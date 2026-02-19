package saga

import (
	"encoding/json"
	"fmt"
	"log"

	ckafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	"gorm.io/gorm"
)

func HandleSagaCommand(p *ckafka.Producer, msg *ckafka.Message) {
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
			return nil // Already processed
		}

		switch cmdType {
		case "complete_order":
			result, err = CompleteOrder(tx, orderID)
		case "fail_order":
			reason, _ := command["data"].(map[string]interface{})["reason"].(string)
			result, err = FailOrder(tx, orderID, reason)
		default:
			log.Printf("Unknown saga command: %s", cmdType)
			return nil
		}
		return err
	})

	if err != nil && result == nil {
		// If error occurred but result is nil, it means it wasn't a duplicate but failed
		log.Printf("Error processing saga command %s: %v", cmdType, err)
	}

	// Publish Event back
	publishSagaEvent(p, sagaID, orderID, cmdType, result, err)
}

func CompleteOrder(tx *gorm.DB, orderID string) (map[string]interface{}, error) {
	err := tx.Model(&models.Order{}).Where("order_id = ?", orderID).Update("status", "COMPLETED").Error
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{"status": "COMPLETED"}, nil
}

func FailOrder(tx *gorm.DB, orderID string, reason string) (map[string]interface{}, error) {
	err := tx.Model(&models.Order{}).Where("order_id = ?", orderID).Update("status", "FAILED").Error
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{"status": "FAILED", "reason": reason}, nil
}

func publishSagaEvent(p *ckafka.Producer, sagaID, orderID, command string, result map[string]interface{}, err error) {
	topic := "saga-events"
	status := "SUCCESS"
	if err != nil {
		status = "FAILURE"
	}

	payload := map[string]interface{}{
		"sagaId":  sagaID,
		"orderId": orderID,
		"command": command,
		"status":  status,
		"data":    result,
	}
	if err != nil {
		payload["error"] = err.Error()
	}

	data, _ := json.Marshal(payload)
	p.Produce(&ckafka.Message{
		TopicPartition: ckafka.TopicPartition{Topic: &topic, Partition: ckafka.PartitionAny},
		Value:          data,
		Key:            []byte(sagaID),
	}, nil)
}
