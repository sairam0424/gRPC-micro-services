package saga

import (
	"encoding/json"
	"fmt"
	"log"
	"time"

	ckafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	"gorm.io/gorm"
)

func HandleSagaCommand(p *ckafka.Producer, msg *ckafka.Message, eventTopic string) {
	var command map[string]interface{}
	if err := json.Unmarshal(msg.Value, &command); err != nil {
		log.Printf("Failed to unmarshal saga command: %v", err)
		return
	}

	sagaID, ok := command["sagaId"].(string)
	if !ok {
		log.Printf("Failed to extract sagaId from saga command")
		return
	}
	orderID, ok := command["orderId"].(string)
	if !ok {
		log.Printf("Failed to extract orderId from saga command")
		return
	}
	cmdType, ok := command["command"].(string)
	if !ok {
		log.Printf("Failed to extract command type from saga command")
		return
	}

	log.Printf("Order Service: Handling Saga command %s for Saga %s", cmdType, sagaID)

	var result map[string]interface{}
	var err error

	// Idempotency: Use a synthetic event ID for saga commands
	eventID := fmt.Sprintf("saga:%s:%s", sagaID, cmdType)

	err = database.DB.Transaction(func(tx *gorm.DB) error {
		if !database.CheckAndRecordEvent(tx, eventID, "order-service") {
			log.Printf("Duplicate saga command ignored: %s", eventID)
			// Return result matching existing state if possible
			// For now, returning nil/nil is safe as publishSagaEvent will handle it
			return nil
		}

		switch cmdType {
		case "complete_order":
			result, err = CompleteOrder(tx, orderID)
		case "fail_order":
			var reason string
			if data, ok := command["data"].(map[string]interface{}); ok && data != nil {
				if r, rOk := data["reason"].(string); rOk {
					reason = r
				}
			}
			result, err = FailOrder(tx, orderID, reason)
		default:
			log.Printf("Unknown saga command: %s", cmdType)
			return fmt.Errorf("unknown saga command: %s", cmdType)
		}
		return err
	})

	if err != nil {
		log.Printf("Error processing saga command %s: %v", cmdType, err)
	}

	// Publish Event back
	publishSagaEvent(p, eventTopic, sagaID, orderID, cmdType, result, err)
}

func CompleteOrder(tx *gorm.DB, orderID string) (map[string]interface{}, error) {
	res := tx.Model(&models.Order{}).Where("order_id = ?", orderID).Update("status", "COMPLETED")
	if res.Error != nil {
		return nil, res.Error
	}
	if res.RowsAffected == 0 {
		return nil, fmt.Errorf("order %s not found for completion", orderID)
	}
	return map[string]interface{}{"status": "COMPLETED"}, nil
}

func FailOrder(tx *gorm.DB, orderID string, reason string) (map[string]interface{}, error) {
	res := tx.Model(&models.Order{}).Where("order_id = ?", orderID).Update("status", "FAILED")
	if res.Error != nil {
		return nil, res.Error
	}
	if res.RowsAffected == 0 {
		return nil, fmt.Errorf("order %s not found for failure", orderID)
	}
	return map[string]interface{}{"status": "FAILED", "reason": reason}, nil
}

func publishSagaEvent(p *ckafka.Producer, topic string, sagaID, orderID, command string, result map[string]interface{}, err error) {
	if topic == "" {
		topic = "saga-events"
	}
	status := "SUCCESS"
	if err != nil {
		status = "FAILURE"
	}

	payload := map[string]interface{}{
		"sagaId":    sagaID,
		"orderId":   orderID,
		"command":   command,
		"status":    status,
		"data":      result,
		"timestamp": time.Now().UnixMilli(),
	}
	if err != nil {
		payload["error"] = err.Error()
	}

	data, err := json.Marshal(payload)
	if err != nil {
		log.Printf("Failed to marshal saga event: %v", err)
		return
	}

	deliveryChan := make(chan ckafka.Event)
	err = p.Produce(&ckafka.Message{
		TopicPartition: ckafka.TopicPartition{Topic: &topic, Partition: ckafka.PartitionAny},
		Value:          data,
		Key:            []byte(sagaID),
	}, deliveryChan)

	if err != nil {
		log.Printf("Failed to produce saga event: %v", err)
		return
	}

	// Wait for delivery report
	e := <-deliveryChan
	m := e.(*ckafka.Message)
	if m.TopicPartition.Error != nil {
		log.Printf("Failed to deliver saga event to Kafka: %v", m.TopicPartition.Error)
	} else {
		log.Printf("Delivered saga event for %s to topic %s", sagaID, *m.TopicPartition.Topic)
	}
	close(deliveryChan)
}
