package kafka

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type Producer struct {
	producer *kafka.Producer
	topic    string
}

func NewProducer(brokers []string, topic string) (*Producer, error) {
	p, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers": brokers[0],
	})
	if err != nil {
		return nil, err
	}
	return &Producer{
		producer: p,
		topic:    topic,
	}, nil
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

	deliveryChan := make(chan kafka.Event)
	err = p.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &p.topic, Partition: kafka.PartitionAny},
		Value:          payload,
	}, deliveryChan)
	if err != nil {
		return err
	}

	e := <-deliveryChan
	m := e.(*kafka.Message)
	if m.TopicPartition.Error != nil {
		return m.TopicPartition.Error
	}

	return nil
}

func (p *Producer) Close() error {
	p.producer.Close()
	return nil
}
