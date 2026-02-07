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

app = FastAPI(title="Order Processing API Gateway", root_path="/api")

# Configuration
ORDER_SERVICE_ADDR = os.getenv("ORDER_SERVICE_ADDR", "localhost:50051")

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItem]

def get_grpc_channel():
    return grpc.insecure_channel(ORDER_SERVICE_ADDR)

@app.get("/")
async def root():
    return {"message": "Welcome to Order Processing API Gateway", "status": "Online"}

@app.post("/orders")
async def create_order(request: CreateOrderRequest):
    try:
        with get_grpc_channel() as channel:
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
        raise HTTPException(status_code=503, detail=f"Order Service unavailable: {e.details()}")

@app.get("/orders")
async def list_orders(customer_id: str = None):
    try:
        with get_grpc_channel() as channel:
            stub = order_pb2_grpc.OrderServiceStub(channel)
            rpc_request = order_pb2.ListOrdersRequest(customer_id=customer_id or "")
            response = stub.ListOrders(rpc_request)
            return {
                "orders": [
                    {
                        "order_id": order.order_id,
                        "customer_id": order.customer_id,
                        "status": order_pb2.OrderStatus.Name(order.status)
                    } for order in response.orders
                ]
            }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Order Service unavailable: {e.details()}")

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    try:
        with get_grpc_channel() as channel:
            stub = order_pb2_grpc.OrderServiceStub(channel)
            rpc_request = order_pb2.GetOrderRequest(order_id=order_id)
            response = stub.GetOrder(rpc_request)
            return {
                "order_id": response.order_id,
                "customer_id": response.customer_id,
                "status": order_pb2.OrderStatus.Name(response.status)
            }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=503, detail=f"Order Service unavailable: {e.details()}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
