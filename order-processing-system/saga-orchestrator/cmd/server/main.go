package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/redis/go-redis/v9"
	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/engine"
	"github.com/sairam0424/gRPC-micro-services/saga-orchestrator/internal/service"
	sagav1 "github.com/sairam0424/gRPC-micro-services/saga-orchestrator/pkg/generated/saga/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

func main() {
	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "redis"
	}
	redisPort := os.Getenv("REDIS_PORT")
	if redisPort == "" {
		redisPort = "6379"
	}
	redisPass := os.Getenv("REDIS_PASSWORD")

	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "kafka:29092"
	}

	log.Printf("Connecting to Redis at %s:%s", redisHost, redisPort)
	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", redisHost, redisPort),
		Password: redisPass,
		DB:       0,
	})

	log.Printf("Initializing Kafka Producer at %s", kafkaBrokers)
	p, err := kafka.NewProducer(&kafka.ConfigMap{"bootstrap.servers": kafkaBrokers})
	if err != nil {
		log.Fatalf("Failed to create Kafka producer: %v", err)
	}
	defer p.Close()

	log.Printf("Initializing Kafka Consumer at %s", kafkaBrokers)
	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": kafkaBrokers,
		"group.id":          "saga-orchestrator-group",
		"auto.offset.reset": "earliest",
	})
	if err != nil {
		log.Fatalf("Failed to create Kafka consumer: %v", err)
	}
	defer c.Close()

	// Initialize Engine
	sagaEngine := engine.NewSagaEngine(rdb, p, c)

	// Start Engine Event Loop
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go sagaEngine.Start(ctx)

	lis, err := net.Listen("tcp", ":50054")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	s := grpc.NewServer()
	sagav1.RegisterSagaServiceServer(s, service.NewSagaService(sagaEngine))
	reflection.Register(s)

	// Health check server
	healthSrv := &http.Server{
		Addr: ":8081",
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"status": "healthy"}`))
		}),
	}
	go func() {
		log.Printf("Health check server listening at :8081")
		if err := healthSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("Health check server failed: %v", err)
		}
	}()

	go func() {
		log.Printf("Saga Orchestrator Service listening at %v", lis.Addr())
		if err := s.Serve(lis); err != nil {
			log.Fatalf("failed to serve: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down Saga Orchestrator...")
	
	cancel() // Stop Saga Engine loop
	
	// Wait a bit for the loop to finish (ideally use a WaitGroup)
	time.Sleep(1 * time.Second)
	
	s.GracefulStop()
	
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	healthSrv.Shutdown(shutdownCtx)
	
	rdb.Close()
}
