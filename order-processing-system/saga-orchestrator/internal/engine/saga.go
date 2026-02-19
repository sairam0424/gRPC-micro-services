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
	// Idempotency: Check if a saga already exists for this orderID
	orderKey := fmt.Sprintf("order:saga:%s", orderID)
	existingSagaID, err := e.redisClient.Get(ctx, orderKey).Result()
	if err == nil && existingSagaID != "" {
		log.Printf("Saga Engine: Saga already exists for Order %s: %s", orderID, existingSagaID)
		return existingSagaID, nil
	}

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

	// Map order to saga for idempotency
	e.redisClient.Set(ctx, orderKey, sagaID, 24*time.Hour)

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

	// Idempotency: Check if this event (command+status) has already been processed for this saga
	processedKey := fmt.Sprintf("saga:processed:%s:%s:%s", sagaID, command, status)
	isProcessed, err := e.redisClient.SetNX(ctx, processedKey, "true", 1*time.Hour).Result()
	if err != nil {
		log.Printf("Saga Engine: CRITICAL: Redis error checking idempotency: %v. Aborting to prevent inconsistent state.", err)
		return
	}
	if !isProcessed {
		log.Printf("Saga Engine: Duplicate event detected for Saga %s, Command %s, Status %s. Skipping.", sagaID, command, status)
		return
	}

	instance, err := e.GetSaga(ctx, sagaID)
	if err != nil {
		log.Printf("Saga Engine: Failed to get saga %s: %v", sagaID, err)
		// Clean up processed key so it can be retried
		e.redisClient.Del(ctx, processedKey)
		return
	}

	// Double check: if status in instance already matches or is more advanced, skip
	if instance.Status == SagaStatusCompleted || instance.Status == SagaStatusFailed {
		log.Printf("Saga Engine: Saga %s already terminal (%s). Skipping event %s (%s).", sagaID, instance.Status, command, status)
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
		// Release stock was successful, now ensure order is failed
		instance.CurrentStep = "FAIL_ORDER"
		e.saveSaga(ctx, instance)
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
		// Initial step failed, move directly to fail_order
		instance.Status = SagaStatusFailed
		instance.CurrentStep = "FAIL_ORDER"
		e.saveSaga(ctx, instance)
		e.publishCommand(instance, "fail_order")

	case "complete_order":
		// Order completion failed, start compensation
		instance.Status = SagaStatusCompensating
		instance.CurrentStep = "RELEASE_STOCK"
		e.saveSaga(ctx, instance)
		e.publishCommand(instance, "release_stock")

	case "release_stock":
		// Compensation failed! In a real system, we'd alert or move to a dead-letter queue / retry.
		// For now, we move to fail_order to ensure order status is updated.
		log.Printf("Saga Engine: CRITICAL: Compensation RELEASE_STOCK failed for Saga %s", instance.ID)
		instance.CurrentStep = "FAIL_ORDER"
		e.saveSaga(ctx, instance)
		e.publishCommand(instance, "fail_order")

	case "fail_order":
		// Even failing failed. This is a terminal terminal error.
		log.Printf("Saga Engine: CRITICAL: Final FAIL_ORDER command failed for Saga %s", instance.ID)
		instance.Status = SagaStatusFailed
		e.saveSaga(ctx, instance)
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

	deliveryChan := make(chan kafka.Event)
	defer close(deliveryChan)

	err := e.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &topic, Partition: kafka.PartitionAny},
		Value:          data,
		Key:            []byte(instance.ID),
	}, deliveryChan)

	if err != nil {
		return fmt.Errorf("failed to produce command %s: %w", command, err)
	}

	report := <-deliveryChan
	m := report.(*kafka.Message)

	if m.TopicPartition.Error != nil {
		return fmt.Errorf("delivery failed for command %s: %w", command, m.TopicPartition.Error)
	}

	log.Printf("Saga Engine: Command %s delivered to topic %s [%d] at offset %v", command, *m.TopicPartition.Topic, m.TopicPartition.Partition, m.TopicPartition.Offset)
	return nil
}
