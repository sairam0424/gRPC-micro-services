package saga

import (
	"encoding/json"
	"log"

	ckafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
)

func HandleSagaCommand(p *ckafka.Producer, msg *ckafka.Message) {
	var command map[string]interface{}
	if err := json.Unmarshal(msg.Value, &command); err != nil {
		log.Printf("Failed to unmarshal saga command: %v", err)
		return
	}

	sagaID := command["sagaId"].(string)
	orderID := command["orderId"].(string)
	cmdType := command["command"].(string)

	log.Printf("Order Service: Handling Saga command %s for Saga %s", cmdType, sagaID)

	var result map[string]interface{}
	var err error

	switch cmdType {
	case "complete_order":
		result, err = CompleteOrder(orderID)
	case "fail_order":
		reason, _ := command["data"].(map[string]interface{})["reason"].(string)
		result, err = FailOrder(orderID, reason)
	default:
		log.Printf("Unknown saga command: %s", cmdType)
		return
	}

	// Publish Event back
	publishSagaEvent(p, sagaID, orderID, cmdType, result, err)
}

func CompleteOrder(orderID string) (map[string]interface{}, error) {
	err := database.DB.Model(&models.Order{}).Where("order_id = ?", orderID).Update("status", "COMPLETED").Error
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{"status": "COMPLETED"}, nil
}

func FailOrder(orderID string, reason string) (map[string]interface{}, error) {
	err := database.DB.Model(&models.Order{}).Where("order_id = ?", orderID).Update("status", "FAILED").Error
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
