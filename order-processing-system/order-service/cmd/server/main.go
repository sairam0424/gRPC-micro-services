package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"sync"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	pb "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/order/v1"
)

type server struct {
	pb.UnimplementedOrderServiceServer
	mu     sync.RWMutex
	orders map[string]*pb.GetOrderResponse
}

func (s *server) CreateOrder(ctx context.Context, req *pb.CreateOrderRequest) (*pb.CreateOrderResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	orderID := fmt.Sprintf("ORD-%d", len(s.orders)+1)
	order := &pb.GetOrderResponse{
		OrderId:    orderID,
		CustomerId: req.CustomerId,
		Items:      req.Items,
		Status:     pb.OrderStatus_ORDER_STATUS_PENDING,
	}
	s.orders[orderID] = order

	log.Printf("Created order: %s for customer: %s", orderID, req.CustomerId)
	return &pb.CreateOrderResponse{
		OrderId: orderID,
		Status:  order.Status,
	}, nil
}

func (s *server) GetOrder(ctx context.Context, req *pb.GetOrderRequest) (*pb.GetOrderResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	order, ok := s.orders[req.OrderId]
	if !ok {
		return nil, status.Errorf(codes.NotFound, "order not found")
	}
	return order, nil
}

func (s *server) ListOrders(ctx context.Context, req *pb.ListOrdersRequest) (*pb.ListOrdersResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var orders []*pb.GetOrderResponse
	for _, order := range s.orders {
		if req.CustomerId == "" || order.CustomerId == req.CustomerId {
			orders = append(orders, order)
		}
	}

	return &pb.ListOrdersResponse{
		Orders: orders,
	}, nil
}

func main() {
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	
	s := grpc.NewServer()
	srv := &server{
		orders: make(map[string]*pb.GetOrderResponse),
	}
	
	pb.RegisterOrderServiceServer(s, srv)
	
	log.Printf("Order Service listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
