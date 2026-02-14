package kafka

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/segmentio/kafka-go"
)

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

func (p *Producer) PublishDLQ(ctx context.Context, originalEvent []byte, err error) error {
	dlqEvent := map[string]interface{}{
		"original_event": string(originalEvent),
		"error":          err.Error(),
		"service":        "order-streamer",
		"retry_exhausted": true,
	}

	payload, marshalErr := json.Marshal(dlqEvent)
	if marshalErr != nil {
		return fmt.Errorf("failed to marshal DLQ event: %w", marshalErr)
	}

	return p.writer.WriteMessages(ctx, kafka.Message{
		Value: payload,
	})
}

func (p *Producer) Close() error {
	return p.writer.Close()
}
