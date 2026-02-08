import asyncio
import json
import grpc
import os
import sys
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

# Ensure generated code is in the path
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
if GENERATED_DIR not in sys.path:
    sys.path.append(GENERATED_DIR)

from stream.v1 import stream_pb2, stream_pb2_grpc

STREAM_SERVICE_ADDR = os.getenv("STREAM_SERVICE_ADDR", "localhost:50053")

async def order_status_streamer(customer_id: str = "") -> AsyncGenerator[str, None]:
    """
    Connects to the Order Streamer gRPC service and yields SSE-formatted events.
    """
    async with grpc.aio.insecure_channel(STREAM_SERVICE_ADDR) as channel:
        stub = stream_pb2_grpc.StreamServiceStub(channel)
        request = stream_pb2.SubscribeOrderUpdatesRequest(customer_id=customer_id)
        
        try:
            # Subscribe to the gRPC server-streaming endpoint
            stream = stub.SubscribeOrderUpdates(request)
            
            # Yield a keep-alive ping immediately
            yield ": keep-alive\n\n"
            
            # Use an async iterator for the stream
            update_iter = stream.__aiter__()
            
            while True:
                try:
                    # Wait for next update or timeout for ping
                    update = await asyncio.wait_for(update_iter.__anext__(), timeout=15.0)
                        
                    data = {
                        "order_id": update.order_id,
                        "customer_id": update.customer_id,
                        "status": update.status,
                        "message": update.message,
                        "items": [
                            {
                                "product_id": item.product_id,
                                "quantity": item.quantity,
                                "price": item.price
                            } for item in update.items
                        ]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                except StopAsyncIteration:
                    break
                except grpc.aio.AioRpcError as e:
                    if e.code() == grpc.StatusCode.CANCELLED:
                        break
                    raise
        except grpc.aio.AioRpcError as e:
            print(f"gRPC streaming error: {e}")
            yield f"data: {json.dumps({'error': 'Stream connection lost', 'details': str(e)})}\n\n"
        except Exception as e:
            print(f"Unexpected streaming error: {e}")
            yield f"data: {json.dumps({'error': 'Internal streaming error'})}\n\n"
