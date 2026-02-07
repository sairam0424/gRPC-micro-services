package main

import (
	"context"
	"log"
	"net"
	"net/http"

	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/proto/order/v1"
)

type server struct {
	pb.UnimplementedOrderServiceServer
}

func (s *server) CreateOrder(ctx context.Context, req *pb.CreateOrderRequest) (*pb.CreateOrderResponse, error) {
	log.Printf("Received CreateOrder for customer: %s", req.GetCustomerId())
	return &pb.CreateOrderResponse{
		OrderId: "ord-123",
		Status:  pb.OrderStatus_ORDER_STATUS_PENDING,
	}, nil
}

func (s *server) GetOrder(ctx context.Context, req *pb.GetOrderRequest) (*pb.GetOrderResponse, error) {
	log.Printf("Received GetOrder for ID: %s", req.GetOrderId())
	return &pb.GetOrderResponse{
		OrderId:    req.GetOrderId(),
		CustomerId: "cust-456",
		Status:     pb.OrderStatus_ORDER_STATUS_PROCESSING,
	}, nil
}

func (s *server) ListOrders(ctx context.Context, req *pb.ListOrdersRequest) (*pb.ListOrdersResponse, error) {
	log.Printf("Received ListOrders for customer: %s", req.GetCustomerId())
	return &pb.ListOrdersResponse{
		Orders: []*pb.GetOrderResponse{
			{OrderId: "ord-1", Status: pb.OrderStatus_ORDER_STATUS_COMPLETED},
		},
	}, nil
}

func main() {
	// 1. Start gRPC server
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	s := grpc.NewServer()
	pb.RegisterOrderServiceServer(s, &server{})

	go func() {
		log.Printf("gRPC server listening at %v", lis.Addr())
		if err := s.Serve(lis); err != nil {
			log.Fatalf("failed to serve gRPC: %v", err)
		}
	}()

	// 2. Start gRPC-Gateway (REST)
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	mux := runtime.NewServeMux()
	opts := []grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}
	err = pb.RegisterOrderServiceHandlerFromEndpoint(ctx, mux, "localhost:50051", opts)
	if err != nil {
		log.Fatalf("failed to register gateway: %v", err)
	}

	// 3. Serve Swagger UI and JSON
	httpMux := http.NewServeMux()
	httpMux.Handle("/", mux)
	
	// Serve the swagger JSON
	httpMux.HandleFunc("/swagger/order.swagger.json", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, "./pkg/generated/proto/order/v1/order.swagger.json")
	})

	// Simple Swagger UI redirect or embedded link
	httpMux.HandleFunc("/swagger/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`
			<!DOCTYPE html>
			<html>
			<head>
				<link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3/swagger-ui.css" >
				<script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"> </script>
			</head>
			<body>
				<div id="swagger-ui"></div>
				<script>
					window.onload = function() {
						SwaggerUIBundle({
							url: "/swagger/order.swagger.json",
							dom_id: '#swagger-ui',
						})
					}
				</script>
			</body>
			</html>
		`))
	})

	log.Printf("REST Gateway + Swagger UI listening at :8080")
	if err := http.ListenAndServe(":8080", httpMux); err != nil {
		log.Fatalf("failed to serve HTTP: %v", err)
	}
}
