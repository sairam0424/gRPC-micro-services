package main

import (
	"context"
	"log"
	"net"
	"os"
	"sync"

	"github.com/sairam0424/gRPC-micro-services/order-streamer/internal/kafka"
	pb "github.com/sairam0424/gRPC-micro-services/order-streamer/pkg/generated/stream/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

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
			// Filter by customer if requested
			if req.CustomerId != "" && event.CustomerID != req.CustomerId {
				continue
			}

			var eventItems []*pb.OrderItem
			for _, item := range event.Items {
				eventItems = append(eventItems, &pb.OrderItem{
					ProductId: item.ProductID,
					Quantity:  item.Quantity,
					Price:     item.Price,
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
	kafkaBrokers := os.Getenv("KAFKA_BROKERS")
	if kafkaBrokers == "" {
		kafkaBrokers = "localhost:9092"
	}

	h := &hub{
		subscribers: make(map[chan kafka.OrderEvent]struct{}),
	}

	consumer := kafka.NewConsumer([]string{kafkaBrokers}, "order-updates", "order-streamer-group")
	go consumer.Start(context.Background())

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

	s := grpc.NewServer()
	pb.RegisterStreamServiceServer(s, &server{hub: h})
	reflection.Register(s)

	log.Printf("Order Streamer Service listening at %v", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
