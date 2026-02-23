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

async def order_status_streamer(customer_id: str = "", stub: stream_pb2_grpc.StreamServiceStub = None) -> AsyncGenerator[str, None]:
    """
    Connects to the Order Streamer gRPC service and yields SSE-formatted events.
    Includes a retry loop to handle transient connection losses.
    """
    retry_count = 0
    max_retries = 10
    retry_delay = 2.0  # seconds

    while retry_count < max_retries:
        try:
            if stub is None:
                async with grpc.aio.insecure_channel(STREAM_SERVICE_ADDR) as channel:
                    temp_stub = stream_pb2_grpc.StreamServiceStub(channel)
                    async for event in _stream_updates(customer_id, temp_stub):
                        yield event
            else:
                async for event in _stream_updates(customer_id, stub):
                    yield event
            
            # If the stream finishes normally (StopAsyncIteration), we break the retry loop
            break
            
        except (grpc.aio.AioRpcError, asyncio.TimeoutError) as e:
            # Only retry on transient connection issues
            is_transient = False
            if isinstance(e, grpc.aio.AioRpcError) and e.code() in [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.INTERNAL]:
                is_transient = True
            elif isinstance(e, asyncio.TimeoutError):
                is_transient = True

            if is_transient:
                retry_count += 1
                print(f"Stream connection lost (attempt {retry_count}/{max_retries}). Retrying in {retry_delay}s... Error: {e}")
                yield f": retry attempt {retry_count}\n\n"
                await asyncio.sleep(retry_delay)
            else:
                # Permanent error or cancellation
                if not (isinstance(e, grpc.aio.AioRpcError) and e.code() == grpc.StatusCode.CANCELLED):
                    yield f"data: {json.dumps({'error': 'Stream connection failed permanently', 'details': str(e)})}\n\n"
                break
        except Exception as e:
            print(f"Unexpected error in streamer loop: {e}")
            yield f"data: {json.dumps({'error': 'Internal streaming error'})}\n\n"
            break

async def _stream_updates(customer_id: str, stub: stream_pb2_grpc.StreamServiceStub) -> AsyncGenerator[str, None]:
    request = stream_pb2.SubscribeOrderUpdatesRequest(customer_id=customer_id)
    
    # Subscribe to the gRPC server-streaming endpoint
    stream = stub.SubscribeOrderUpdates(request)
    
    # Yield a keep-alive ping immediately to acknowledge connection
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
                        "price": item.price_cents # Fixed field name while at it, based on proto
                    } for item in update.items
                ]
            }
            yield f"data: {json.dumps(data)}\n\n"
        except asyncio.TimeoutError:
            yield ": keep-alive\n\n"
        except StopAsyncIteration:
            break
        # Error handling is now primarily in the caller (order_status_streamer)
        # but we still catch CANCELLED here for clean break
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.CANCELLED:
                break
            raise # Propagate to retry loop
