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
	EventType  string      `json:"event_type"` // e.g., "order.created", "order.updated"
	OrderID    string      `json:"order_id"`
	CustomerID string      `json:"customer_id"`
	Status     string      `json:"status"`
	Message    string      `json:"message"`
	Items      []OrderItem `json:"items"`
}

type Producer struct {
	writer *kafka.Writer
}

func NewProducer(brokers []string, topic string) *Producer {
	return &Producer{
		writer: &kafka.Writer{
			Addr:     kafka.TCP(brokers...),
			Topic:    topic,
			Balancer: &kafka.LeastBytes{},
		},
	}
}

func (p *Producer) PublishOrderEvent(ctx context.Context, event OrderEvent) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}

	err = p.writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte(event.OrderID),
		Value: payload,
	})

	if err != nil {
		log.Printf("Failed to publish event to Kafka: %v", err)
		return err
	}

	log.Printf("Published event to Kafka: %s (Status: %s)", event.OrderID, event.Status)
	return nil
}

func (p *Producer) Close() error {
	return p.writer.Close()
}
