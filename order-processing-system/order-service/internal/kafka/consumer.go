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
	"gorm.io/gorm"
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

	topics := []string{topic, "media.events"}
	err := c.consumer.SubscribeTopics(topics, nil)
	if err != nil {
		log.Fatalf("Failed to subscribe to topics: %v", err)
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
			// Generic event type check
			// We can try to peek the event type or use a generic proto message
			// For simplicity, we'll try to deserialize into different types
			
			if msg.Topic == "media.events" {
				mediaEvent := &eventsv1.MediaUploadedEvent{}
				err = c.deserializer.DeserializeInto(msg.Topic, msg.Value, mediaEvent)
				if err == nil {
					if mediaEvent.EntityType == "order" {
						err = database.DB.Transaction(func(tx *gorm.DB) error {
							if !database.CheckAndRecordEvent(tx, mediaEvent.EventId, "order-service") {
								return nil
							}
							return c.handleMediaUploaded(tx, mediaEvent)
						})
						if err != nil {
							log.Printf("Error handling media event: %v", err)
						}
					}
					c.consumer.CommitMessage(msg)
					continue
				}
			}

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
			err = database.DB.Transaction(func(tx *gorm.DB) error {
				if !database.CheckAndRecordEvent(tx, event.EventId, "order-service") {
					log.Printf("Duplicate event ignored: %s", event.EventId)
					return nil
				}

				switch event.EventType {
				case "inventory.reserved":
					c.handleInventoryReserved(tx, event)
				case "inventory.failed":
					c.handleInventoryFailed(tx, event)
				}
				return nil
			})
		}
	}
}

func (c *OrderConsumer) handleInventoryReserved(tx *gorm.DB, event *eventsv1.InventoryReservedEvent) {
	log.Printf("Handling inventory.reserved for order %s", event.OrderId)

	// Update order status to COMPLETED
	err := tx.Model(&models.Order{}).Where("order_id = ?", event.OrderId).Update("status", "COMPLETED").Error
	if err != nil {
		log.Printf("Failed to update order status in DB: %v", err)
		return
	}

	// Publish order.updated event
	c.publishOrderUpdate(event, "COMPLETED")
}

func (c *OrderConsumer) handleInventoryFailed(tx *gorm.DB, event *eventsv1.InventoryReservedEvent) {
	log.Printf("Handling inventory.failed for order %s: %s", event.OrderId, event.Message)

	// Update order status to FAILED
	err := tx.Model(&models.Order{}).Where("order_id = ?", event.OrderId).Update("status", "FAILED").Error
	if err != nil {
		log.Printf("Failed to update order status in DB: %v", err)
		return
	}

	// Publish order.updated event
	c.publishOrderUpdate(event, "FAILED")
}

func (c *OrderConsumer) handleMediaUploaded(tx *gorm.DB, event *eventsv1.MediaUploadedEvent) error {
	log.Printf("Associating media %s with order %s", event.MediaId, event.EntityId)

	var order models.Order
	if err := tx.Where("order_id = ?", event.EntityId).First(&order).Error; err != nil {
		return fmt.Errorf("failed to find order: %w", err)
	}

	// Append media ID if not already present
	found := false
	for _, m := range order.MediaIDs {
		if m == event.MediaId {
			found = true
			break
		}
	}
	if !found {
		order.MediaIDs = append(order.MediaIDs, event.MediaId)
		if err := tx.Save(&order).Error; err != nil {
			return fmt.Errorf("failed to update order media IDs: %w", err)
		}
	}

	return nil
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
