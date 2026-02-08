from fastapi import FastAPI, HTTPException
from typing import List
from pydantic import BaseModel
import grpc
import os
import sys

# Ensure generated code is in the path
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
sys.path.append(GENERATED_DIR)

from order.v1 import order_pb2, order_pb2_grpc
from inventory.v1 import inventory_pb2, inventory_pb2_grpc

app = FastAPI(title="Order Processing API Gateway", root_path="/api")

# Configuration
ORDER_SERVICE_ADDR = os.getenv("ORDER_SERVICE_ADDR", "localhost:50051")
INVENTORY_SERVICE_ADDR = os.getenv("INVENTORY_SERVICE_ADDR", "localhost:50052")

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItem]

def get_order_channel():
    return grpc.insecure_channel(ORDER_SERVICE_ADDR)

def get_inventory_channel():
    return grpc.insecure_channel(INVENTORY_SERVICE_ADDR)

@app.get("/")
async def root():
    return {"message": "Welcome to Order Processing API Gateway", "status": "Online"}

@app.get("/inventory")
async def list_inventory():
    try:
        with get_inventory_channel() as channel:
            stub = inventory_pb2_grpc.InventoryServiceStub(channel)
            # We don't have a ListInventory in gRPC yet, but we can check a few known ones 
            # or just rely on the REST API of inventory-service.
            # For simplicity, let's assume we want to check a specific product or a list
            # In a real system, we'd add ListInventory to proto.
            # For now, let's just provide a health check or a placeholder.
            return {"message": "Inventory management via gRPC active"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Inventory Service unavailable: {e}")

@app.post("/orders")
async def create_order(request: CreateOrderRequest):
    try:
        with get_order_channel() as channel:
            stub = order_pb2_grpc.OrderServiceStub(channel)
            
            # Map items
            rpc_items = [
                order_pb2.OrderItem(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.price
                ) for item in request.items
            ]
            
            rpc_request = order_pb2.CreateOrderRequest(
                customer_id=request.customer_id,
                items=rpc_items
            )
            
            response = stub.CreateOrder(rpc_request)
            return {
                "order_id": response.order_id,
                "status": order_pb2.OrderStatus.Name(response.status)
            }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            raise HTTPException(status_code=400, detail=f"Order rejected: {e.details()}")
        raise HTTPException(status_code=503, detail=f"Order Service error: {e.details()}")

@app.get("/orders")
async def list_orders(customer_id: str = None):
    try:
        with get_order_channel() as channel:
            stub = order_pb2_grpc.OrderServiceStub(channel)
            rpc_request = order_pb2.ListOrdersRequest(customer_id=customer_id or "")
            response = stub.ListOrders(rpc_request)
            return {
                "orders": [
                    {
                        "order_id": order.order_id,
                        "customer_id": order.customer_id,
                        "status": order_pb2.OrderStatus.Name(order.status),
                        "items": [
                            {
                                "product_id": item.product_id,
                                "quantity": item.quantity,
                                "price": item.price
                            } for item in order.items
                        ]
                    } for order in response.orders
                ]
            }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Order Service unavailable: {e.details()}")

from .streaming import order_status_streamer
from fastapi.responses import StreamingResponse

@app.get("/orders/events")
async def stream_order_updates(customer_id: str = None):
    """
    Server-Sent Events (SSE) endpoint for real-time order status updates.
    """
    return StreamingResponse(
        order_status_streamer(customer_id or ""),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for Nginx
        }
    )

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    try:
        with get_order_channel() as channel:
            stub = order_pb2_grpc.OrderServiceStub(channel)
            rpc_request = order_pb2.GetOrderRequest(order_id=order_id)
            response = stub.GetOrder(rpc_request)
            return {
                "order_id": response.order_id,
                "customer_id": response.customer_id,
                "status": order_pb2.OrderStatus.Name(response.status),
                "items": [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "price": item.price
                    } for item in response.items
                ]
            }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=503, detail=f"Order Service unavailable: {e.details()}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
