package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/sairam0424/gRPC-micro-services/order-service/internal/client/inventory"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/database"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/kafka"
	"github.com/sairam0424/gRPC-micro-services/order-service/internal/models"
	invpb "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/inventory/v1"
	pb "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/order/v1"
	"gorm.io/gorm"
)

type server struct {
	pb.UnimplementedOrderServiceServer
	inventoryClient *inventory.Client
	kafkaProducer   *kafka.Producer
}

func (s *server) CreateOrder(ctx context.Context, req *pb.CreateOrderRequest) (*pb.CreateOrderResponse, error) {
	// 1. Prepare inventory items
	var invItems []*invpb.InventoryItem
	for _, item := range req.Items {
		invItems = append(invItems, &invpb.InventoryItem{
			ProductId: item.ProductId,
			Quantity:  item.Quantity,
		})
	}

	// 2. Reserve stock
	tempOrderID := fmt.Sprintf("TEMP-%d", time.Now().UnixNano())
	success, msg, err := s.inventoryClient.ReserveStock(ctx, tempOrderID, invItems)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to communicate with inventory service: %v", err)
	}
	if !success {
		return nil, status.Errorf(codes.FailedPrecondition, "inventory reservation failed: %s", msg)
	}

	// Generate Order ID
	orderID := fmt.Sprintf("ORD-%d", time.Now().UnixNano())

	// Save to DB
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

	if err := database.DB.Create(&dbOrder).Error; err != nil {
		return nil, status.Errorf(codes.Internal, "failed to save order: %v", err)
	}

	var eventItems []kafka.OrderItem
	for _, item := range req.Items {
		eventItems = append(eventItems, kafka.OrderItem{
			ProductID: item.ProductId,
			Quantity:  item.Quantity,
			Price:     item.Price,
		})
	}

	// 3. Publish PENDING event
	err = s.kafkaProducer.PublishOrderEvent(context.Background(), kafka.OrderEvent{
		OrderID:    orderID,
		CustomerID: req.CustomerId,
		Status:     "PENDING",
		Message:    "Order created and awaiting processing",
		Items:      eventItems,
	})
	if err != nil {
		log.Printf("Non-critical error publishing PENDING event: %v", err)
	}

	// 4. Simulate background processing
	go func(oid, cid string) {
		time.Sleep(5 * time.Second)
		// Update DB
		database.DB.Model(&models.Order{}).Where("order_id = ?", oid).Update("status", "COMPLETED")

		err = s.kafkaProducer.PublishOrderEvent(context.Background(), kafka.OrderEvent{
			OrderID:    oid,
			CustomerID: cid,
			Status:     "COMPLETED",
			Message:    "Order processed successfully",
			Items:      eventItems,
		})
		if err != nil {
			log.Printf("Non-critical error publishing COMPLETED event: %v", err)
		}
	}(orderID, req.CustomerId)

	log.Printf("Created order: %s for customer: %s", orderID, req.CustomerId)
	return &pb.CreateOrderResponse{
		OrderId: orderID,
		Status:  pb.OrderStatus_ORDER_STATUS_PENDING,
	}, nil
}

func (s *server) GetOrder(ctx context.Context, req *pb.GetOrderRequest) (*pb.GetOrderResponse, error) {
	var dbOrder models.Order
	if err := database.DB.Preload("Items").Where("order_id = ?", req.OrderId).First(&dbOrder).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, status.Errorf(codes.NotFound, "order not found")
		}
		return nil, status.Errorf(codes.Internal, "database error: %v", err)
	}

	return mapDBOrderToPB(&dbOrder), nil
}

func mapDBOrderToPB(dbOrder *models.Order) *pb.GetOrderResponse {
	var orderStatus pb.OrderStatus
	switch dbOrder.Status {
	case "PENDING":
		orderStatus = pb.OrderStatus_ORDER_STATUS_PENDING
	case "COMPLETED":
		orderStatus = pb.OrderStatus_ORDER_STATUS_COMPLETED
	default:
		orderStatus = pb.OrderStatus_ORDER_STATUS_UNSPECIFIED
	}

	var pbItems []*pb.OrderItem
	for _, item := range dbOrder.Items {
		pbItems = append(pbItems, &pb.OrderItem{
			ProductId: item.ProductID,
			Quantity:  item.Quantity,
			Price:     item.Price,
		})
	}

	return &pb.GetOrderResponse{
		OrderId:    dbOrder.OrderID,
		CustomerId: dbOrder.CustomerID,
		Items:      pbItems,
		Status:     orderStatus,
	}
}

func (s *server) ListOrders(ctx context.Context, req *pb.ListOrdersRequest) (*pb.ListOrdersResponse, error) {
	var dbOrders []models.Order
	query := database.DB.Preload("Items")
	if req.CustomerId != "" {
		query = query.Where("customer_id = ?", req.CustomerId)
	}

	if err := query.Find(&dbOrders).Error; err != nil {
		return nil, status.Errorf(codes.Internal, "database error: %v", err)
	}

	var orders []*pb.GetOrderResponse
	for _, dbOrder := range dbOrders {
		orders = append(orders, mapDBOrderToPB(&dbOrder))
	}

	return &pb.ListOrdersResponse{
		Orders: orders,
	}, nil
}

func main() {
	inventoryAddr := os.Getenv("INVENTORY_SERVICE_ADDR")
	if inventoryAddr == "" {
		inventoryAddr = "localhost:50052"
	}

	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "localhost:9092"
	}

	invClient, err := inventory.NewClient(inventoryAddr)
	if err != nil {
		log.Fatalf("failed to create inventory client: %v", err)
	}
	defer invClient.Close()

	database.InitDB()

	producer := kafka.NewProducer([]string{kafkaBrokers}, "order-updates")
	defer producer.Close()

	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	s := grpc.NewServer()
	srv := &server{
		inventoryClient: invClient,
		kafkaProducer:   producer,
	}

	pb.RegisterOrderServiceServer(s, srv)

	log.Printf("Order Service listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
