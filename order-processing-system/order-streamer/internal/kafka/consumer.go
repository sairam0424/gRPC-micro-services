package kafka

import (
	"context"
	"encoding/json"
	"log"

	"github.com/segmentio/kafka-go"
)

type OrderItem struct {
	ProductID string  `json:"product_id"`
	Quantity  int32   `json:"quantity"`
	Price     float64 `json:"price"`
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
	reader *kafka.Reader
	Events chan OrderEvent
}

func NewConsumer(brokers []string, topic, groupID string) *Consumer {
	return &Consumer{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers:  brokers,
			Topic:    topic,
			GroupID:  groupID,
			MinBytes: 10e3, // 10KB
			MaxBytes: 10e6, // 10MB
		}),
		Events: make(chan OrderEvent, 100),
	}
}

func (c *Consumer) Start(ctx context.Context) {
	log.Printf("Starting Kafka consumer on topic: %s", c.reader.Config().Topic)
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

		log.Printf("Received event: %s (Status: %s)", event.OrderID, event.Status)
		c.Events <- event
	}
}

func (c *Consumer) Close() error {
	return c.reader.Close()
}
