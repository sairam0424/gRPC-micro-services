package inventory

import (
	"context"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sairam0424/gRPC-micro-services/order-service/pkg/generated/inventory/v1"
)

type Client struct {
	conn   *grpc.ClientConn
	client pb.InventoryServiceClient
}

func NewClient(addr string) (*Client, error) {
	conn, err := grpc.Dial(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, err
	}

	return &Client{
		conn:   conn,
		client: pb.NewInventoryServiceClient(conn),
	}, nil
}

func (c *Client) Close() error {
	return c.conn.Close()
}

func (c *Client) ReserveStock(ctx context.Context, orderID string, items []*pb.InventoryItem) (bool, string, error) {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	resp, err := c.client.ReserveStock(ctx, &pb.ReserveStockRequest{
		OrderId: orderID,
		Items:   items,
	})
	if err != nil {
		log.Printf("Failed to reserve stock: %v", err)
		return false, "Inventory service error", err
	}

	return resp.Success, resp.Message, nil
}

func (c *Client) ReleaseStock(ctx context.Context, orderID string, items []*pb.InventoryItem) error {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	_, err := c.client.ReleaseStock(ctx, &pb.ReleaseStockRequest{
		OrderId: orderID,
		Items:   items,
	})
	return err
}
