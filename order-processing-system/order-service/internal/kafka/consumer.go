package kafka

import (
	"context"
	"encoding/json"
	"log"

	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	"github.com/segmentio/kafka-go"
)

type OrderConsumer struct {
	reader   *kafka.Reader
	producer *Producer
}

func NewOrderConsumer(brokers []string, topic, groupID string, producer *Producer) *OrderConsumer {
	return &OrderConsumer{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers:  brokers,
			Topic:    topic,
			GroupID:  groupID,
			MinBytes: 10e3,
			MaxBytes: 10e6,
		}),
		producer: producer,
	}
}

func (c *OrderConsumer) Start(ctx context.Context) {
	log.Printf("Order Service Consumer started on topic: %s", c.reader.Config().Topic)
	for {
		m, err := c.reader.ReadMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			log.Printf("Error reading message: %v", err)
			continue
		}

		var event OrderEvent
		if err := json.Unmarshal(m.Value, &event); err != nil {
			log.Printf("Error unmarshaling event: %v", err)
			continue
		}

		// Only handle inventory result events
		if event.EventType == "inventory.reserved" || event.EventType == "inventory.failed" {
			c.handleInventoryResult(event)
		}
	}
}

func (c *OrderConsumer) handleInventoryResult(event OrderEvent) {
	log.Printf("Handling inventory result for order %s: %s", event.OrderID, event.EventType)

	newStatus := "COMPLETED"
	if event.EventType == "inventory.failed" {
		newStatus = "FAILED"
	}

	// 1. Update DB
	err := database.DB.Model(&models.Order{}).Where("order_id = ?", event.OrderID).Update("status", newStatus).Error
	if err != nil {
		log.Printf("Failed to update order status in DB: %v", err)
		return
	}

	// 2. Publish order.updated event for streamer
	updateEvent := OrderEvent{
		EventType:  "order.updated",
		OrderID:    event.OrderID,
		CustomerID: event.CustomerID,
		Status:     newStatus,
		Message:    event.Message,
		Items:      event.Items,
	}

	err = c.producer.PublishOrderEvent(context.Background(), updateEvent)
	if err != nil {
		log.Printf("Failed to publish order.updated event: %v", err)
	}
}

func (c *OrderConsumer) Close() error {
	return c.reader.Close()
}
