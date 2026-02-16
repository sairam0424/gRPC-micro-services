package kafka

import (
	"context"
	"fmt"
	"log"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde/protobuf"
	eventsv1 "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/events/v1"
)

type Producer struct {
	producer   *kafka.Producer
	serializer *protobuf.Serializer
	topic      string
}

func NewProducer(brokers []string, topic string, schemaRegistryURL string) (*Producer, error) {
	p, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers": brokers[0],
		"client.id":         "order-service-producer",
		"acks":              "all",
	})
	if err != nil {
		return nil, err
	}

	client, err := schemaregistry.NewClient(schemaregistry.NewConfig(schemaRegistryURL))
	if err != nil {
		return nil, fmt.Errorf("failed to create schema registry client: %w", err)
	}

	ser, err := protobuf.NewSerializer(client, serde.ValueSerde, protobuf.NewSerializerConfig())
	if err != nil {
		return nil, fmt.Errorf("failed to create protobuf serializer: %w", err)
	}

	return &Producer{
		producer:   p,
		serializer: ser,
		topic:      topic,
	}, nil
}

func (p *Producer) PublishOrderEvent(ctx context.Context, event *eventsv1.OrderCreatedEvent) error {
	// Serialize the protobuf message using official serializer
	payload, err := p.serializer.Serialize(p.topic, event)
	if err != nil {
		return fmt.Errorf("failed to serialize protobuf: %w", err)
	}

	// Produce message
	deliveryChan := make(chan kafka.Event)
	err = p.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &p.topic, Partition: kafka.PartitionAny},
		Key:            []byte(event.OrderId),
		Value:          payload,
	}, deliveryChan)

	if err != nil {
		return fmt.Errorf("failed to produce message: %w", err)
	}

	// Wait for delivery report
	e := <-deliveryChan
	m := e.(*kafka.Message)

	if m.TopicPartition.Error != nil {
		log.Printf("Failed to deliver message: %v\n", m.TopicPartition.Error)
		return m.TopicPartition.Error
	}

	log.Printf("Published event to Kafka: %s (Type: %s, Status: %s)\n",
		event.OrderId, event.EventType, event.Status)
	return nil
}

func (p *Producer) Close() error {
	p.producer.Flush(5000)
	p.serializer.Close()
	p.producer.Close()
	return nil
}
