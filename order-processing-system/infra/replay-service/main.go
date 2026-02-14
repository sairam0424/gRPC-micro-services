package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/segmentio/kafka-go"
)

type DLQEvent struct {
	OriginalEvent interface{} `json:"original_event"`
	Error         string      `json:"error"`
	Service       string      `json:"service"`
}

type ReplayRequest struct {
	SourceTopic string `json:"source"`
	TargetTopic string `json:"target"`
	Brokers     string `json:"brokers"`
}

type ReplayResponse struct {
	Status  string `json:"status"`
	Count   int    `json:"count"`
	Message string `json:"message"`
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}

	http.HandleFunc("/api/replay", handleReplay)
	http.HandleFunc("/api/health", handleHealth)

	log.Printf("Replay Service starting on port %s...", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func handleReplay(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ReplayRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.SourceTopic == "" || req.TargetTopic == "" {
		http.Error(w, "source and target topics are required", http.StatusBadRequest)
		return
	}

	brokers := req.Brokers
	if brokers == "" {
		brokers = os.Getenv("KAFKA_BROKERS")
	}
	if brokers == "" {
		brokers = "kafka:29092"
	}

	count, err := performReplay(brokers, req.SourceTopic, req.TargetTopic)
	if err != nil {
		log.Printf("Replay failed: %v", err)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(ReplayResponse{
			Status:  "error",
			Message: err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(ReplayResponse{
		Status: "success",
		Count:  count,
	})
}

func performReplay(brokers, source, target string) (int, error) {
	log.Printf("Starting replay from %s to %s...", source, target)

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     []string{brokers},
		Topic:       source,
		GroupID:     fmt.Sprintf("replay-group-%d", time.Now().Unix()),
		StartOffset: kafka.FirstOffset,
	})
	defer reader.Close()

	writer := &kafka.Writer{
		Addr:     kafka.TCP(brokers),
		Topic:    target,
		Balancer: &kafka.LeastBytes{},
	}
	defer writer.Close()

	count := 0
	// Use a shorter timeout to detect end of topic
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		m, err := reader.ReadMessage(ctx)
		cancel()

		if err != nil {
			// If we timeout, we assume we've read everything CURRENTLY in the DLQ
			log.Printf("Finished or timed out: %v", err)
			break
		}

		var dlqEvent DLQEvent
		if err := json.Unmarshal(m.Value, &dlqEvent); err != nil {
			log.Printf("Error parsing DLQ event at offset %d: %v", m.Offset, err)
			continue
		}

		payload, err := json.Marshal(dlqEvent.OriginalEvent)
		if err != nil {
			log.Printf("Error marshaling original event: %v", err)
			continue
		}

		err = writer.WriteMessages(context.Background(), kafka.Message{
			Value: payload,
		})
		if err != nil {
			return count, fmt.Errorf("failed to write to target topic: %w", err)
		}

		count++
		log.Printf("Replayed message from offset %d", m.Offset)
	}

	return count, nil
}

