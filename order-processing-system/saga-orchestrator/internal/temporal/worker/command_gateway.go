package worker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type CommandRequest struct {
	SagaID         string                 `json:"sagaId"`
	OrderID        string                 `json:"orderId"`
	Command        string                 `json:"command"`
	Data           map[string]interface{} `json:"data,omitempty"`
	IdempotencyKey string                 `json:"idempotencyKey,omitempty"`
}

type CommandResponse struct {
	SagaID    string                 `json:"sagaId"`
	OrderID   string                 `json:"orderId"`
	Command   string                 `json:"command"`
	Status    string                 `json:"status"`
	Data      map[string]interface{} `json:"data,omitempty"`
	Error     string                 `json:"error,omitempty"`
	Timestamp int64                  `json:"timestamp,omitempty"`
}

type CommandExecutor interface {
	ExecuteCommand(ctx context.Context, req CommandRequest) (*CommandResponse, error)
}

type GatewayConfig struct {
	KafkaBrokers  string
	CommandTopic  string
	EventTopic    string
	ConsumerGroup string
}

type CommandGateway struct {
	cfg      GatewayConfig
	producer *kafka.Producer
	consumer *kafka.Consumer

	mu       sync.Mutex
	inflight map[string]chan *CommandResponse
}

func DefaultGatewayConfig(kafkaBrokers string) GatewayConfig {
	hostname, _ := os.Hostname()
	if hostname == "" {
		hostname = "unknown"
	}
	return GatewayConfig{
		KafkaBrokers:  kafkaBrokers,
		CommandTopic:  envOrDefault("SAGA_COMMAND_TOPIC", "saga-commands"),
		EventTopic:    envOrDefault("SAGA_EVENT_TOPIC", "saga-events"),
		ConsumerGroup: envOrDefault("TEMPORAL_SAGA_EVENT_CONSUMER_GROUP", fmt.Sprintf("temporal-saga-worker-%s", hostname)),
	}
}

func NewCommandGateway(cfg GatewayConfig) (*CommandGateway, error) {
	producer, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers": cfg.KafkaBrokers,
		"client.id":         "temporal-saga-worker-producer",
		"acks":              "all",
	})
	if err != nil {
		return nil, fmt.Errorf("create producer: %w", err)
	}

	consumer, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers":  cfg.KafkaBrokers,
		"group.id":           cfg.ConsumerGroup,
		"auto.offset.reset":  "latest",
		"enable.auto.commit": false,
	})
	if err != nil {
		producer.Close()
		return nil, fmt.Errorf("create consumer: %w", err)
	}

	return &CommandGateway{
		cfg:      cfg,
		producer: producer,
		consumer: consumer,
		inflight: make(map[string]chan *CommandResponse),
	}, nil
}

func (g *CommandGateway) Start(ctx context.Context) error {
	if err := g.consumer.SubscribeTopics([]string{g.cfg.EventTopic}, nil); err != nil {
		return fmt.Errorf("subscribe to %s: %w", g.cfg.EventTopic, err)
	}

	go g.pollLoop(ctx)
	return nil
}

func (g *CommandGateway) Close() {
	g.consumer.Close()
	g.producer.Flush(2000)
	g.producer.Close()
}

func (g *CommandGateway) ExecuteCommand(ctx context.Context, req CommandRequest) (*CommandResponse, error) {
	if req.SagaID == "" || req.OrderID == "" || req.Command == "" {
		return nil, fmt.Errorf("missing required command fields")
	}

	key := g.responseKey(req.SagaID, req.Command)
	respCh := make(chan *CommandResponse, 1)

	g.mu.Lock()
	if _, exists := g.inflight[key]; exists {
		g.mu.Unlock()
		return nil, fmt.Errorf("command %s already in-flight for saga %s", req.Command, req.SagaID)
	}
	g.inflight[key] = respCh
	g.mu.Unlock()

	defer func() {
		g.mu.Lock()
		delete(g.inflight, key)
		g.mu.Unlock()
	}()

	if err := g.publish(req); err != nil {
		return nil, err
	}

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case resp := <-respCh:
		if strings.EqualFold(resp.Status, "FAILURE") {
			if resp.Error != "" {
				return resp, errors.New(resp.Error)
			}
			return resp, fmt.Errorf("command %s failed", req.Command)
		}
		return resp, nil
	}
}

func (g *CommandGateway) publish(req CommandRequest) error {
	payload := map[string]interface{}{
		"sagaId":  req.SagaID,
		"orderId": req.OrderID,
		"command": req.Command,
		"data":    req.Data,
	}
	if req.IdempotencyKey != "" {
		payload["idempotencyKey"] = req.IdempotencyKey
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal command payload: %w", err)
	}

	delivery := make(chan kafka.Event, 1)
	defer close(delivery)

	err = g.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &g.cfg.CommandTopic, Partition: kafka.PartitionAny},
		Key:            []byte(req.SagaID),
		Value:          data,
	}, delivery)
	if err != nil {
		return fmt.Errorf("publish command: %w", err)
	}

	select {
	case report := <-delivery:
		message, ok := report.(*kafka.Message)
		if !ok {
			return fmt.Errorf("unexpected delivery report type %T", report)
		}
		if message.TopicPartition.Error != nil {
			return fmt.Errorf("delivery error: %w", message.TopicPartition.Error)
		}
		return nil
	case <-time.After(10 * time.Second):
		return fmt.Errorf("timed out waiting for command delivery")
	}
}

func (g *CommandGateway) pollLoop(ctx context.Context) {
	log.Printf("Temporal Command Gateway: consuming events from %s with group %s", g.cfg.EventTopic, g.cfg.ConsumerGroup)
	for {
		select {
		case <-ctx.Done():
			return
		default:
			ev := g.consumer.Poll(100)
			if ev == nil {
				continue
			}

			switch event := ev.(type) {
			case *kafka.Message:
				g.handleMessage(event)
				_, _ = g.consumer.CommitMessage(event)
			case kafka.Error:
				log.Printf("Temporal Command Gateway: kafka error: %v", event)
			}
		}
	}
}

func (g *CommandGateway) handleMessage(msg *kafka.Message) {
	var response CommandResponse
	if err := json.Unmarshal(msg.Value, &response); err != nil {
		log.Printf("Temporal Command Gateway: failed to unmarshal event: %v", err)
		return
	}

	key := g.responseKey(response.SagaID, response.Command)
	g.mu.Lock()
	ch := g.inflight[key]
	g.mu.Unlock()

	if ch == nil {
		return
	}

	select {
	case ch <- &response:
	default:
	}
}

func (g *CommandGateway) responseKey(sagaID string, command string) string {
	return fmt.Sprintf("%s|%s", sagaID, command)
}

func envOrDefault(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}
