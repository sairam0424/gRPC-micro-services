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

	"google.golang.org/protobuf/proto"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/sairam0424/gRPC-micro-services/order-service/internal/client/inventory"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/kafka"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	eventsv1 "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/events/v1"
	orderv1 "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/order/v1"
	"gorm.io/gorm"

	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
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
			semconv.ServiceNameKey.String("order-service"),
		)),
	)
	otel.SetTracerProvider(tp)
	return tp, nil
}

type server struct {
	orderv1.UnimplementedOrderServiceServer
	inventoryClient *inventory.Client
	kafkaProducer   *kafka.Producer
}

func (s *server) CreateOrder(ctx context.Context, req *orderv1.CreateOrderRequest) (*orderv1.CreateOrderResponse, error) {
	// Generate Order ID
	orderID := fmt.Sprintf("ORD-%d", time.Now().UnixNano())

	// Use Transaction for Outbox Pattern
	err := database.DB.Transaction(func(tx *gorm.DB) error {
		// 1. Create Order
		dbOrder := models.Order{
			OrderID:    orderID,
			CustomerID: req.CustomerId,
			Status:     "PENDING",
		}

		for _, item := range req.Items {
			dbOrder.Items = append(dbOrder.Items, models.OrderItem{
				OrderID:   orderID,
				ProductID: item.ProductId,
				Quantity:  item.Quantity,
				Price:     item.Price,
			})
		}

		if err := tx.Create(&dbOrder).Error; err != nil {
			return err
		}

		// 2. Create Outbox Record with Protobuf event
		eventItems := make([]*eventsv1.OrderItem, 0, len(req.Items))
		for _, item := range req.Items {
			eventItems = append(eventItems, &eventsv1.OrderItem{
				ProductId: item.ProductId,
				Quantity:  item.Quantity,
				Price:     item.Price,
			})
		}

		event := &eventsv1.OrderCreatedEvent{
			EventId:    fmt.Sprintf("order_created_%s", orderID),
			EventType:  "order.created",
			OrderId:    orderID,
			CustomerId: req.CustomerId,
			Status:     "PENDING",
			Message:    "Order created and awaiting processing",
			Items:      eventItems,
			Timestamp:  time.Now().UnixMilli(),
		}

		payload, err := proto.Marshal(event)
		if err != nil {
			return err
		}

		outbox := models.Outbox{
			AggregateType: "Order",
			AggregateID:   orderID,
			EventType:     "order.created",
			Payload:       payload,
			CreatedAt:     time.Now(),
		}

		if err := tx.Create(&outbox).Error; err != nil {
			return err
		}

		return nil
	})

	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to create order and outbox: %v", err)
	}

	log.Printf("Created order: %s and outbox record for customer: %s", orderID, req.CustomerId)
	return &orderv1.CreateOrderResponse{
		OrderId: orderID,
		Status:  orderv1.OrderStatus_ORDER_STATUS_PENDING,
	}, nil
}

func (s *server) GetOrder(ctx context.Context, req *orderv1.GetOrderRequest) (*orderv1.GetOrderResponse, error) {
	var dbOrder models.Order
	if err := database.DB.Preload("Items").Where("order_id = ?", req.OrderId).First(&dbOrder).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, status.Errorf(codes.NotFound, "order not found")
		}
		return nil, status.Errorf(codes.Internal, "database error: %v", err)
	}

	return mapDBOrderToPB(&dbOrder), nil
}

func mapDBOrderToPB(dbOrder *models.Order) *orderv1.GetOrderResponse {
	var orderStatus orderv1.OrderStatus
	switch dbOrder.Status {
	case "PENDING":
		orderStatus = orderv1.OrderStatus_ORDER_STATUS_PENDING
	case "COMPLETED":
		orderStatus = orderv1.OrderStatus_ORDER_STATUS_COMPLETED
	default:
		orderStatus = orderv1.OrderStatus_ORDER_STATUS_UNSPECIFIED
	}

	var pbItems []*orderv1.OrderItem
	for _, item := range dbOrder.Items {
		pbItems = append(pbItems, &orderv1.OrderItem{
			ProductId: item.ProductID,
			Quantity:  item.Quantity,
			Price:     item.Price,
		})
	}

	return &orderv1.GetOrderResponse{
		OrderId:    dbOrder.OrderID,
		CustomerId: dbOrder.CustomerID,
		Items:      pbItems,
		Status:     orderStatus,
	}
}

func (s *server) ListOrders(ctx context.Context, req *orderv1.ListOrdersRequest) (*orderv1.ListOrdersResponse, error) {
	var dbOrders []models.Order
	query := database.DB.Preload("Items")
	if req.CustomerId != "" {
		query = query.Where("customer_id = ?", req.CustomerId)
	}

	if err := query.Find(&dbOrders).Error; err != nil {
		return nil, status.Errorf(codes.Internal, "database error: %v", err)
	}

	var orders []*orderv1.GetOrderResponse
	for _, dbOrder := range dbOrders {
		orders = append(orders, mapDBOrderToPB(&dbOrder))
	}

	return &orderv1.ListOrdersResponse{
		Orders: orders,
	}, nil
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

	inventoryAddr := os.Getenv("INVENTORY_SERVICE_ADDR")
	if inventoryAddr == "" {
		inventoryAddr = "localhost:50052"
	}

	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "localhost:9092"
	}

	schemaRegistryURL := os.Getenv("SCHEMA_REGISTRY_URL")
	if schemaRegistryURL == "" {
		schemaRegistryURL = "http://localhost:8081"
	}

	invClient, err := inventory.NewClient(inventoryAddr)
	if err != nil {
		log.Fatalf("failed to create inventory client: %v", err)
	}
	defer invClient.Close()

	database.InitDB()

	producer, err := kafka.NewProducer([]string{kafkaBrokers}, "order-events", schemaRegistryURL)
	if err != nil {
		log.Fatalf("failed to create kafka producer: %v", err)
	}
	defer producer.Close()

	consumer, err := kafka.NewOrderConsumer([]string{kafkaBrokers}, "inventory-events", "order-service-group", producer)
	if err != nil {
		log.Fatalf("failed to create kafka consumer: %v", err)
	}
	go consumer.Start(context.Background(), "inventory-events")
	defer consumer.Close()

	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	s := grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)
	srv := &server{
		inventoryClient: invClient,
		kafkaProducer:   producer,
	}

	orderv1.RegisterOrderServiceServer(s, srv)
	
	// Create cancellable context for background workers
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start Outbox Relay goroutine
	go startOutboxRelay(ctx, database.DB, producer)

	// Handle Graceful Shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-quit
		log.Println("Shutting down Order Service...")
		cancel() // Stop background workers
		s.GracefulStop()
	}()

	// Start health check server
	go func() {
		mux := http.NewServeMux()
		mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			
			dbStatus := "connected"
			db, err := database.DB.DB()
			if err != nil || db.Ping() != nil {
				dbStatus = "disconnected"
			}
			
			// For this demo, we assume kafka is connected if the producer is initialized
			// In Go, better check would be writer.Stats() or Dial
			kafkaStatus := "connected"
			if producer == nil {
				kafkaStatus = "disconnected"
			}

			status := "healthy"
			if dbStatus != "connected" || kafkaStatus != "connected" {
				status = "unhealthy"
				w.WriteHeader(http.StatusServiceUnavailable)
			} else {
				w.WriteHeader(http.StatusOK)
			}

			fmt.Fprintf(w, `{"status": "%s", "version": "0.1.0", "checks": {"database": "%s", "kafka": "%s"}}`, status, dbStatus, kafkaStatus)
		})
		log.Printf("Health check server listening at :8081")
		if err := http.ListenAndServe(":8081", mux); err != nil {
			log.Printf("Health check server failed: %v", err)
		}
	}()

	log.Printf("Order Service listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}

func startOutboxRelay(ctx context.Context, db *gorm.DB, producer *kafka.Producer) {
	log.Println("Starting Outbox Relay worker...")
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			var messages []models.Outbox
			// Fetch up to 100 messages to process
			if err := db.Order("created_at asc").Limit(100).Find(&messages).Error; err != nil {
				log.Printf("Outbox Relay: failed to fetch messages: %v", err)
				continue
			}

			for _, msg := range messages {
				// We need to unmarshal to get the proper Protobuf message for the producer
				// The producer expectations: context, proto.Message
				// But wait, the producer's PublishOrderEvent specifically takes *eventsv1.OrderCreatedEvent?
				// Let's check internal/kafka/producer.go again.
				
				// Re-reading internal/kafka/producer.go:
				// func (p *Producer) PublishOrderEvent(ctx context.Context, event *eventsv1.OrderCreatedEvent) error
				
				var event eventsv1.OrderCreatedEvent
				if err := proto.Unmarshal(msg.Payload, &event); err != nil {
					log.Printf("Outbox Relay: failed to unmarshal payload for ID %d: %v", msg.ID, err)
					// If it's unmarshalable, we might want to move it to a DLQ or just skip it
					continue
				}

				if err := producer.PublishOrderEvent(ctx, &event); err != nil {
					log.Printf("Outbox Relay: failed to publish message %d to Kafka: %v", msg.ID, err)
					continue
				}

				// Success: remove from outbox
				if err := db.Delete(&msg).Error; err != nil {
					log.Printf("Outbox Relay: failed to delete message %d from outbox: %v", msg.ID, err)
				}
			}
		}
	}
}
