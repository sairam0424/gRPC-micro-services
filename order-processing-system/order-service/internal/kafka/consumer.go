package kafka

import (
	"context"
	"encoding/binary"
	"fmt"
	"log"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	eventsv1 "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/events/v1"
	"google.golang.org/protobuf/proto"
)

type OrderConsumer struct {
	consumer *kafka.Consumer
	producer *Producer
}

func NewOrderConsumer(brokers []string, topic, groupID string, producer *Producer) (*OrderConsumer, error) {
	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": brokers[0],
		"group.id":          groupID,
		"auto.offset.reset": "earliest",
	})
	if err != nil {
		return nil, err
	}

	return &OrderConsumer{
		consumer: c,
		producer: producer,
	}, nil
}

func (c *OrderConsumer) Start(ctx context.Context, topic string) {
	log.Printf("Order Service Consumer started on topic: %s", topic)
	
	err := c.consumer.Subscribe(topic, nil)
	if err != nil {
		log.Fatalf("Failed to subscribe to topic: %v", err)
	}

	for {
		select {
		case <-ctx.Done():
			return
		default:
			msg, err := c.consumer.ReadMessage(-1)
			if err != nil {
				log.Printf("Error reading message: %v", err)
				continue
			}

			// Deserialize Confluent wire format Protobuf message
			event, err := c.deserializeEvent(msg.Value)
			if err != nil {
				log.Printf("Error deserializing event: %v", err)
				continue
			}

			// Handle different event types
			switch event.EventType {
			case "inventory.reserved":
				c.handleInventoryReserved(event)
			case "inventory.failed":
				c.handleInventoryFailed(event)
			}
		}
	}
}

func (c *OrderConsumer) deserializeEvent(value []byte) (*eventsv1.InventoryReservedEvent, error) {
	// Confluent wire format: [magic_byte][schema_id][protobuf_data]
	if len(value) < 5 {
		return nil, fmt.Errorf("message too short for Confluent wire format")
	}

	magicByte := value[0]
	if magicByte != 0 {
		return nil, fmt.Errorf("invalid magic byte: %d", magicByte)
	}

	schemaID := binary.BigEndian.Uint32(value[1:5])
	log.Printf("Received message with schema ID: %d", schemaID)

	protobufData := value[5:]

	// Try to deserialize as InventoryReservedEvent first
	event := &eventsv1.InventoryReservedEvent{}
	if err := proto.Unmarshal(protobufData, event); err != nil {
		// If that fails, try InventoryFailedEvent
		failedEvent := &eventsv1.InventoryFailedEvent{}
		if err := proto.Unmarshal(protobufData, failedEvent); err != nil {
			return nil, fmt.Errorf("failed to unmarshal protobuf: %w", err)
		}
		// Convert InventoryFailedEvent to InventoryReservedEvent structure for unified handling
		event = &eventsv1.InventoryReservedEvent{
			EventId:    failedEvent.EventId,
			EventType:  failedEvent.EventType,
			OrderId:    failedEvent.OrderId,
			CustomerId: failedEvent.CustomerId,
			Status:     failedEvent.Status,
			Message:    failedEvent.Message,
			Items:      failedEvent.Items,
			Timestamp:  failedEvent.Timestamp,
		}
	}

	return event, nil
}

func (c *OrderConsumer) handleInventoryReserved(event *eventsv1.InventoryReservedEvent) {
	log.Printf("Handling inventory.reserved for order %s", event.OrderId)

	// Update order status to COMPLETED
	err := database.DB.Model(&models.Order{}).Where("order_id = ?", event.OrderId).Update("status", "COMPLETED").Error
	if err != nil {
		log.Printf("Failed to update order status in DB: %v", err)
		return
	}

	// Publish order.updated event
	c.publishOrderUpdate(event, "COMPLETED")
}

func (c *OrderConsumer) handleInventoryFailed(event *eventsv1.InventoryReservedEvent) {
	log.Printf("Handling inventory.failed for order %s: %s", event.OrderId, event.Message)

	// Update order status to FAILED
	err := database.DB.Model(&models.Order{}).Where("order_id = ?", event.OrderId).Update("status", "FAILED").Error
	if err != nil {
		log.Printf("Failed to update order status in DB: %v", err)
		return
	}

	// Publish order.updated event
	c.publishOrderUpdate(event, "FAILED")
}

func (c *OrderConsumer) publishOrderUpdate(event *eventsv1.InventoryReservedEvent, status string) {
	updateEvent := &eventsv1.OrderCreatedEvent{
		EventId:    fmt.Sprintf("order_updated_%s", event.OrderId),
		EventType:  "order.updated",
		OrderId:    event.OrderId,
		CustomerId: event.CustomerId,
		Status:     status,
		Message:    event.Message,
		Items:      event.Items,
		Timestamp:  event.Timestamp,
	}

	err := c.producer.PublishOrderEvent(context.Background(), updateEvent)
	if err != nil {
		log.Printf("Failed to publish order.updated event: %v", err)
	}
}

func (c *OrderConsumer) Close() error {
	return c.consumer.Close()
}
