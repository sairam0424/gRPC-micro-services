package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/cenkalti/backoff/v5"
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
	reader          *kafka.Reader
	dlqProducer     *Producer
	Events          chan OrderEvent
	processedEvents sync.Map // Simple in-memory idempotency cache: eventID -> timestamp
}

func NewConsumer(brokers []string, topic, groupID string, dlqProducer *Producer) *Consumer {
	return &Consumer{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers:  brokers,
			Topic:    topic,
			GroupID:  groupID,
			MinBytes: 10e3, // 10KB
			MaxBytes: 10e6, // 10MB
		}),
		dlqProducer: dlqProducer,
		Events:      make(chan OrderEvent, 100),
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

		// Retry logic with exponential backoff
		operation := func() (struct{}, error) {
			var event OrderEvent
			if err := json.Unmarshal(m.Value, &event); err != nil {
				return struct{}{}, backoff.Permanent(fmt.Errorf("poison pill: %w", err))
			}

			// Idempotency check
			eventID := event.OrderID
			if eventID == "" {
				eventID = fmt.Sprintf("%x", m.Value[:16])
			}
			if _, loaded := c.processedEvents.LoadOrStore(eventID, time.Now()); loaded {
				log.Printf("Duplicate event ignored: %s", eventID)
				return struct{}{}, nil
			}

			log.Printf("Received event: %s (Status: %s)", event.OrderID, event.Status)
			
			select {
			case c.Events <- event:
				return struct{}{}, nil
			case <-ctx.Done():
				return struct{}{}, ctx.Err()
			}
		}

		_, err = backoff.Retry(ctx, operation, backoff.WithMaxTries(3))
		if err != nil {
			log.Printf("Processing failed after retries: %v. Sending to DLQ...", err)
			if c.dlqProducer != nil {
				if dlqErr := c.dlqProducer.PublishDLQ(ctx, m.Value, err); dlqErr != nil {
					log.Printf("CRITICAL: Failed to publish to DLQ: %v", dlqErr)
				}
			}
		}
	}
}

func (c *Consumer) Ping(ctx context.Context) error {
	// Just check if we can dial the first broker
	conn, err := kafka.DialContext(ctx, "tcp", c.reader.Config().Brokers[0])
	if err != nil {
		return err
	}
	conn.Close()
	return nil
}

func (c *Consumer) Close() error {
	return c.reader.Close()
}
