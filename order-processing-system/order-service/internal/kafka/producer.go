package kafka

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	eventsv1 "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/events/v1"
	"google.golang.org/protobuf/proto"
)

type SchemaRegistryClient struct {
	url        string
	httpClient *http.Client
}

func NewSchemaRegistryClient(url string) *SchemaRegistryClient {
	return &SchemaRegistryClient{
		url: url,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (s *SchemaRegistryClient) GetSchemaID(subject string, schema string) (int, error) {
	payload := map[string]interface{}{
		"schema":     schema,
		"schemaType": "PROTOBUF",
	}
	body, _ := json.Marshal(payload)

	resp, err := s.httpClient.Post(
		fmt.Sprintf("%s/subjects/%s/versions", s.url, subject),
		"application/vnd.schemaregistry.v1+json",
		bytes.NewBuffer(body),
	)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return 0, fmt.Errorf("schema registry error: %s", string(bodyBytes))
	}

	var result struct {
		ID int `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, err
	}

	return result.ID, nil
}

type Producer struct {
	producer       *kafka.Producer
	schemaRegistry *SchemaRegistryClient
	topic          string
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

	return &Producer{
		producer:       p,
		schemaRegistry: NewSchemaRegistryClient(schemaRegistryURL),
		topic:          topic,
	}, nil
}

func (p *Producer) PublishOrderEvent(ctx context.Context, event *eventsv1.OrderCreatedEvent) error {
	// Serialize the protobuf message
	payload, err := proto.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal protobuf: %w", err)
	}

	// Get schema ID from Schema Registry
	// For simplicity, we'll use a hardcoded schema ID of 1 for now
	// In production, you would register the schema and get the ID
	schemaID := 1

	// Confluent wire format: [0][schema_id][protobuf_data]
	// Magic byte (0) + 4-byte schema ID + protobuf payload
	wireFormat := make([]byte, 5+len(payload))
	wireFormat[0] = 0 // Magic byte
	binary.BigEndian.PutUint32(wireFormat[1:5], uint32(schemaID))
	copy(wireFormat[5:], payload)

	// Produce message
	deliveryChan := make(chan kafka.Event)
	err = p.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &p.topic, Partition: kafka.PartitionAny},
		Key:            []byte(event.OrderId),
		Value:          wireFormat,
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
	p.producer.Close()
	return nil
}
