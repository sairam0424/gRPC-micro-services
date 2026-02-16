package kafka

import (
	"context"
	"fmt"
	"log"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde/protobuf"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	eventsv1 "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/events/v1"
)

type OrderConsumer struct {
	consumer     *kafka.Consumer
	producer     *Producer
	deserializer *protobuf.Deserializer
}

func NewOrderConsumer(brokers []string, topic, groupID string, producer *Producer, schemaRegistryURL string) (*OrderConsumer, error) {
	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": brokers[0],
		"group.id":          groupID,
		"auto.offset.reset": "earliest",
	})
	if err != nil {
		return nil, err
	}

	client, err := schemaregistry.NewClient(schemaregistry.NewConfig(schemaRegistryURL))
	if err != nil {
		return nil, fmt.Errorf("failed to create schema registry client: %w", err)
	}

	deser, err := protobuf.NewDeserializer(client, serde.ValueSerde, protobuf.NewDeserializerConfig())
	if err != nil {
		return nil, fmt.Errorf("failed to create protobuf deserializer: %w", err)
	}

	return &OrderConsumer{
		consumer:     c,
		producer:     producer,
		deserializer: deser,
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

			// Deserialize using official deserializer
			// Note: The deserializer will automatically pick the right message type if registered
			// or we can specify the target type.
			event := &eventsv1.InventoryReservedEvent{}
			err = c.deserializer.DeserializeInto(topic, msg.Value, event)
			if err != nil {
				// Try InventoryFailedEvent if it fails (simplistic handling)
				failedEvent := &eventsv1.InventoryFailedEvent{}
				if err2 := c.deserializer.DeserializeInto(topic, msg.Value, failedEvent); err2 == nil {
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
				} else {
					log.Printf("Error deserializing event from topic %s: %v (Failed also as inventory.failed: %v)", topic, err, err2)
					continue
				}
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
	c.deserializer.Close()
	return c.consumer.Close()
}
