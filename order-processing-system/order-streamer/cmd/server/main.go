package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/sairam0424/gRPC-micro-services/order-streamer/internal/kafka"
	pb "github.com/sairam0424/gRPC-micro-services/order-streamer/pkg/generated/stream/v1"

	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"

	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)
func initTracer() (*sdktrace.TracerProvider, error) {
	ctx := context.Background()
	otelEndpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if otelEndpoint == "" {
		otelEndpoint = "localhost:4317"
	}

	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithInsecure(),
		otlptracegrpc.WithEndpoint(otelEndpoint),
	)
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceNameKey.String("order-streamer"),
		)),
	)
	otel.SetTracerProvider(tp)
	return tp, nil
}

type hub struct {
	mu          sync.RWMutex
	subscribers map[chan kafka.OrderEvent]struct{}
}

func (h *hub) subscribe() chan kafka.OrderEvent {
	h.mu.Lock()
	defer h.mu.Unlock()
	ch := make(chan kafka.OrderEvent, 10)
	h.subscribers[ch] = struct{}{}
	return ch
}

func (h *hub) unsubscribe(ch chan kafka.OrderEvent) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.subscribers, ch)
	close(ch)
}

func (h *hub) broadcast(event kafka.OrderEvent) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for ch := range h.subscribers {
		select {
		case ch <- event:
		default:
			log.Printf("Subscriber buffer full, dropping message for one stream")
		}
	}
}

type server struct {
	pb.UnimplementedStreamServiceServer
	hub *hub
}

func (s *server) SubscribeOrderUpdates(req *pb.SubscribeOrderUpdatesRequest, stream pb.StreamService_SubscribeOrderUpdatesServer) error {
	log.Printf("New subscription request for customer: %s", req.CustomerId)
	ch := s.hub.subscribe()
	defer s.hub.unsubscribe(ch)

	for {
		select {
		case event := <-ch:
			// Filter by event type
			if event.EventType != "order.created" && event.EventType != "order.updated" {
				continue
			}

			// Filter by customer if requested
			if req.CustomerId != "" && event.CustomerID != req.CustomerId {
				continue
			}

			var eventItems []*pb.OrderItem
			for _, item := range event.Items {
				eventItems = append(eventItems, &pb.OrderItem{
					ProductId:  item.ProductID,
					Quantity:   item.Quantity,
					PriceCents: item.PriceCents,
				})
			}

			err := stream.Send(&pb.OrderStatusUpdate{
				OrderId:    event.OrderID,
				CustomerId: event.CustomerID,
				Status:     event.Status,
				Message:    event.Message,
				Items:      eventItems,
			})
			if err != nil {
				log.Printf("Error sending stream update: %v", err)
				return err
			}
		case <-stream.Context().Done():
			log.Printf("Subscription closed for customer: %s", req.CustomerId)
			return nil
		}
	}
}

func main() {
	tp, err := initTracer()
	if err != nil {
		log.Fatal(err)
	}
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			log.Printf("Error shutting down tracer provider: %v", err)
		}
	}()

	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "localhost:9092"
	}

	h := &hub{
		subscribers: make(map[chan kafka.OrderEvent]struct{}),
	}

	schemaRegistryURL := os.Getenv("SCHEMA_REGISTRY_URL")
	if schemaRegistryURL == "" {
		schemaRegistryURL = "http://localhost:8081"
	}

	dlqProducer, err := kafka.NewProducer([]string{kafkaBrokers}, "order-streamer.dlq")
	if err != nil {
		log.Fatalf("failed to create dlq producer: %v", err)
	}
	defer dlqProducer.Close()

	consumer, err := kafka.NewConsumer([]string{kafkaBrokers}, "order-events", "order-streamer-group", dlqProducer, schemaRegistryURL)
	if err != nil {
		log.Fatalf("failed to create consumer: %v", err)
	}
	go consumer.Start(context.Background(), "order-events")

	// Route events from Kafka to the hub
	go func() {
		for event := range consumer.Events {
			h.broadcast(event)
		}
	}()

	lis, err := net.Listen("tcp", ":50053")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	s := grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)
	pb.RegisterStreamServiceServer(s, &server{hub: h})
	reflection.Register(s)

	// Start health check server
	go func() {
		http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			if err := consumer.Ping(ctx); err != nil {
				w.WriteHeader(http.StatusServiceUnavailable)
				fmt.Fprintf(w, "kafka connectivity error: %v", err)
				return
			}
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("healthy"))
		})
		log.Printf("Health check server listening at :8089")
		if err := http.ListenAndServe(":8089", nil); err != nil {
			log.Printf("Health check server failed: %v", err)
		}
	}()

	log.Printf("Order Streamer Service listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
