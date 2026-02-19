package kafka

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde/protobuf"
	eventsv1 "github.com/sairam0424/gRPC-micro-services/order-streamer/pkg/generated/events/v1"
)

type OrderItem struct {
	ProductID string `json:"product_id"`
	Quantity  uint32 `json:"quantity"`
	PriceCents int64  `json:"price_cents"`
}

type OrderEvent struct {
	EventType  string      `json:"event_type"`
	OrderID    string      `json:"order_id"`
	CustomerID string      `json:"customer_id"`
	Status     string      `json:"status"`
	Message    string      `json:"message"`
	Items      []OrderItem `json:"items"`
}

type Consumer struct {
	consumer        *kafka.Consumer
	dlqProducer     *Producer
	Events          chan OrderEvent
	deserializer    *protobuf.Deserializer
	processedEvents sync.Map // Simple in-memory idempotency cache: eventID -> timestamp
}

func NewConsumer(brokers []string, topic, groupID string, dlqProducer *Producer, schemaRegistryURL string) (*Consumer, error) {
	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": brokers[0],
		"group.id":          groupID,
		"auto.offset.reset": "earliest",
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create consumer: %w", err)
	}

	sr, err := schemaregistry.NewClient(schemaregistry.NewConfig(schemaRegistryURL))
	if err != nil {
		return nil, fmt.Errorf("failed to create schema registry client: %w", err)
	}

	deser, err := protobuf.NewDeserializer(sr, serde.ValueSerde, protobuf.NewDeserializerConfig())
	if err != nil {
		return nil, fmt.Errorf("failed to create protobuf deserializer: %w", err)
	}

	return &Consumer{
		consumer:    c,
		dlqProducer: dlqProducer,
		Events:      make(chan OrderEvent, 100),
		deserializer: deser,
	}, nil
}

func (c *Consumer) Start(ctx context.Context, topic string) {
	if err := c.consumer.Subscribe(topic, nil); err != nil {
		log.Printf("Failed to subscribe to topic %s: %v", topic, err)
		return
	}

	log.Printf("Starting Kafka consumer on topic: %s", topic)
	for {
		ev := c.consumer.Poll(100)
		if ev == nil {
			continue
		}

		switch e := ev.(type) {
		case *kafka.Message:
			var eventObj eventsv1.OrderCreatedEvent
			err := c.deserializer.DeserializeInto(*e.TopicPartition.Topic, e.Value, &eventObj)
			if err != nil {
				log.Printf("Deserialization failed: %v. Sending to DLQ...", err)
				if c.dlqProducer != nil {
					if dlqErr := c.dlqProducer.PublishDLQ(ctx, e.Value, err); dlqErr != nil {
						log.Printf("CRITICAL: Failed to publish to DLQ: %v", dlqErr)
					}
				}
				continue
			}

			// Map to internal OrderEvent
			items := make([]OrderItem, len(eventObj.Items))
			for i, item := range eventObj.Items {
				items[i] = OrderItem{
					ProductID:  item.ProductId,
					Quantity:   item.Quantity,
					PriceCents: item.PriceCents,
				}
			}

			event := OrderEvent{
				EventType:  eventObj.EventType,
				OrderID:    eventObj.OrderId,
				CustomerID: eventObj.CustomerId,
				Status:     eventObj.Status,
				Message:    eventObj.Message,
				Items:      items,
			}

			// Idempotency check: Use OrderID + Status to allow status transitions
			dedupeKey := fmt.Sprintf("%s:%s", event.OrderID, event.Status)
			if _, loaded := c.processedEvents.LoadOrStore(dedupeKey, time.Now()); loaded {
				log.Printf("Duplicate event ignored: %s", dedupeKey)
				continue
			}

			log.Printf("Received event: %s (Status: %s)", event.OrderID, event.Status)
			
			select {
			case c.Events <- event:
			case <-ctx.Done():
				return
			}

		case kafka.Error:
			log.Printf("Consumer error: %v", e)
			if e.IsFatal() {
				return
			}
		default:
			// Ignore other event types
		}
	}
}

func (c *Consumer) Ping(ctx context.Context) error {
	_, err := c.consumer.GetMetadata(nil, false, 2000)
	return err
}

func (c *Consumer) Close() error {
	c.deserializer.Close()
	return c.consumer.Close()
}
