package main

import (
	"context"
	"log"
	"net"

	"google.golang.org/grpc"
	// pb "github.com/sairamugge/order-processing/order/v1" // Generated code will be here
)

type server struct {
	// pb.UnimplementedOrderServiceServer
}

func main() {
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	s := grpc.NewServer()
	// pb.RegisterOrderServiceServer(s, &server{})
	log.Printf("server listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
