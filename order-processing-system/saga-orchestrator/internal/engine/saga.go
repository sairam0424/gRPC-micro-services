package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/redis/go-redis/v9"
)

type SagaStatus string

const (
	SagaStatusStarted      SagaStatus = "STARTED"
	SagaStatusInProgress   SagaStatus = "IN_PROGRESS"
	SagaStatusCompleted    SagaStatus = "COMPLETED"
	SagaStatusFailed       SagaStatus = "FAILED"
	SagaStatusCompensating SagaStatus = "COMPENSATING"
)

type SagaInstance struct {
	ID          string                 `json:"id"`
	OrderID     string                 `json:"orderId"`
	Status      SagaStatus             `json:"status"`
	CurrentStep string                 `json:"currentStep"`
	Data        map[string]interface{} `json:"data"`
	CreatedAt   time.Time              `json:"createdAt"`
	UpdatedAt   time.Time              `json:"updatedAt"`
}

type SagaEngine struct {
	redisClient *redis.Client
	producer    *kafka.Producer
	consumer    *kafka.Consumer
}

func NewSagaEngine(redisClient *redis.Client, producer *kafka.Producer, consumer *kafka.Consumer) *SagaEngine {
	return &SagaEngine{
		redisClient: redisClient,
		producer:    producer,
		consumer:    consumer,
	}
}

func (e *SagaEngine) StartOrderSaga(ctx context.Context, orderID string, items interface{}) (string, error) {
	sagaID := fmt.Sprintf("saga_%s_%d", orderID, time.Now().Unix())

	instance := &SagaInstance{
		ID:          sagaID,
		OrderID:     orderID,
		Status:      SagaStatusStarted,
		CurrentStep: "RESERVE_STOCK",
		Data: map[string]interface{}{
			"items": items,
		},
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	if err := e.saveSaga(ctx, instance); err != nil {
		return "", err
	}

	// Publish First Command to Kafka
	if err := e.publishCommand(instance, "reserve_stock"); err != nil {
		return "", err
	}

	return sagaID, nil
}

func (e *SagaEngine) Start(ctx context.Context) {
	if err := e.consumer.SubscribeTopics([]string{"saga-events"}, nil); err != nil {
		log.Fatalf("Failed to subscribe to saga-events: %v", err)
	}

	log.Println("Saga Engine: Started event processor")
	for {
		select {
		case <-ctx.Done():
			return
		default:
			ev := e.consumer.Poll(100)
			if ev == nil {
				continue
			}

			switch event := ev.(type) {
			case *kafka.Message:
				e.handleEvent(ctx, event)
			case kafka.Error:
				log.Printf("Saga Engine: Kafka error: %v", event)
			}
		}
	}
}

func (e *SagaEngine) handleEvent(ctx context.Context, msg *kafka.Message) {
	var event map[string]interface{}
	if err := json.Unmarshal(msg.Value, &event); err != nil {
		log.Printf("Saga Engine: Failed to unmarshal event: %v", err)
		return
	}

	sagaID, ok := event["sagaId"].(string)
	if !ok {
		log.Printf("Saga Engine: Missing or invalid sagaId in event")
		return
	}
	status, ok := event["status"].(string)
	if !ok {
		log.Printf("Saga Engine: Missing or invalid status in event")
		return
	}
	command, ok := event["command"].(string)
	if !ok {
		log.Printf("Saga Engine: Missing or invalid command in event")
		return
	}

	instance, err := e.GetSaga(ctx, sagaID)
	if err != nil {
		log.Printf("Saga Engine: Failed to get saga %s: %v", sagaID, err)
		return
	}

	log.Printf("Saga Engine: Processing event %s (%s) for Saga %s", command, status, sagaID)

	if status == "SUCCESS" {
		e.handleNextStep(ctx, instance, command)
	} else {
		e.handleFailure(ctx, instance, command, event["error"])
	}
}

func (e *SagaEngine) handleNextStep(ctx context.Context, instance *SagaInstance, lastCmd string) {
	switch lastCmd {
	case "reserve_stock":
		instance.CurrentStep = "COMPLETE_ORDER"
		instance.Status = SagaStatusInProgress
		e.saveSaga(ctx, instance)
		e.publishCommand(instance, "complete_order")

	case "complete_order":
		instance.Status = SagaStatusCompleted
		instance.CurrentStep = "DONE"
		e.saveSaga(ctx, instance)
		log.Printf("Saga Engine: Saga %s COMPLETED successfully", instance.ID)

	case "release_stock":
		e.publishCommand(instance, "fail_order")
	case "fail_order":
		instance.Status = SagaStatusFailed
		instance.CurrentStep = "FAILED"
		e.saveSaga(ctx, instance)
		log.Printf("Saga Engine: Saga %s FAILED (Compensated)", instance.ID)
	}
}

func (e *SagaEngine) handleFailure(ctx context.Context, instance *SagaInstance, lastCmd string, err interface{}) {
	log.Printf("Saga Engine: Command %s failed for Saga %s: %v", lastCmd, instance.ID, err)

	switch lastCmd {
	case "reserve_stock":
		instance.Status = SagaStatusFailed
		instance.CurrentStep = "FAIL_ORDER"
		e.saveSaga(ctx, instance)
		e.publishCommand(instance, "fail_order")

	case "complete_order":
		instance.Status = SagaStatusCompensating
		instance.CurrentStep = "RELEASE_STOCK"
		e.saveSaga(ctx, instance)
		e.publishCommand(instance, "release_stock")
	}
}

func (e *SagaEngine) GetSaga(ctx context.Context, sagaID string) (*SagaInstance, error) {
	val, err := e.redisClient.Get(ctx, fmt.Sprintf("saga:%s", sagaID)).Result()
	if err != nil {
		return nil, err
	}

	var instance SagaInstance
	if err := json.Unmarshal([]byte(val), &instance); err != nil {
		return nil, err
	}

	return &instance, nil
}

func (e *SagaEngine) saveSaga(ctx context.Context, instance *SagaInstance) error {
	instance.UpdatedAt = time.Now()
	data, err := json.Marshal(instance)
	if err != nil {
		return err
	}
	return e.redisClient.Set(ctx, fmt.Sprintf("saga:%s", instance.ID), data, 24*time.Hour).Err()
}

func (e *SagaEngine) publishCommand(instance *SagaInstance, command string) error {
	topic := "saga-commands"
	payload := map[string]interface{}{
		"sagaId":  instance.ID,
		"orderId": instance.OrderID,
		"command": command,
		"data":    instance.Data,
	}

	data, _ := json.Marshal(payload)

	return e.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &topic, Partition: kafka.PartitionAny},
		Value:          data,
		Key:            []byte(instance.ID),
	}, nil)
}
