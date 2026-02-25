from fastapi import FastAPI, HTTPException, Depends, Request
import httpx
import asyncio
from typing import List, Optional
import functools
from contextlib import asynccontextmanager
from pydantic import BaseModel
import grpc
import os
import sys
import logging
from opentelemetry import trace, metrics, _logs
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient
from opentelemetry.instrumentation.logging import LoggingInstrumentor
import hashlib
import json
from elasticsearch import AsyncElasticsearch

# Ensure generated code is in the path
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
sys.path.append(GENERATED_DIR)

from order.v1 import order_pb2, order_pb2_grpc
from inventory.v1 import inventory_pb2, inventory_pb2_grpc
from stream.v1 import stream_pb2, stream_pb2_grpc

# Logger
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize persistent gRPC channels
    logger.info("Initializing persistent gRPC channels...")
    app.state.order_channel = grpc.aio.insecure_channel(ORDER_SERVICE_ADDR)
    app.state.inventory_channel = grpc.aio.insecure_channel(INVENTORY_SERVICE_ADDR)
    app.state.stream_channel = grpc.aio.insecure_channel(os.getenv("STREAM_SERVICE_ADDR", "localhost:50053"))
    
    app.state.order_stub = order_pb2_grpc.OrderServiceStub(app.state.order_channel)
    app.state.inventory_stub = inventory_pb2_grpc.InventoryServiceStub(app.state.inventory_channel)
    app.state.stream_stub = stream_pb2_grpc.StreamServiceStub(app.state.stream_channel)
    
    # Elasticsearch Client init
    es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    es_port = os.getenv("ELASTICSEARCH_PORT", "9200")
    app.state.es_client = AsyncElasticsearch([f"http://{es_host}:{es_port}"])

    yield

    # Shutdown: Close channels
    logger.info("Closing gRPC channels and clients...")
    await app.state.es_client.close()
    await app.state.order_channel.close()
    await app.state.inventory_channel.close()
    await app.state.stream_channel.close()

app = FastAPI(title="Order Processing API Gateway", lifespan=lifespan)

import sys
import os

# Add src directory to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import verify_jwt
from .bloom_filter import bloom_manager
from .rate_limiter import rate_limiter
from .load_shedder import load_shedder

# Prometheus Metrics
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

RATELIMIT_HITS = Counter("ratelimit_hits_total", "Total requests allowed by rate limiter")
RATELIMIT_REJECTS = Counter("ratelimit_rejects_total", "Total requests rejected by rate limiter")
LOADSHED_REJECTS = Counter("loadshed_rejects_total", "Total requests rejected by load shedder")
SYSTEM_STRESS = Gauge("system_stress_level", "Current system stress level (0.0 to 1.0)")

@app.get("/metrics")
async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Configuration
ORDER_SERVICE_ADDR = os.getenv("ORDER_SERVICE_ADDR", "localhost:50051")
INVENTORY_SERVICE_ADDR = os.getenv("INVENTORY_SERVICE_ADDR", "localhost:50052")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")

logger.info(f"API Gateway starting with Order Service: {ORDER_SERVICE_ADDR}, Inventory Service: {INVENTORY_SERVICE_ADDR}")

# OpenTelemetry Setup
resource = Resource.create({"service.name": "api-gateway"})

# Tracing
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)))

# Metrics
metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True))
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# Logs
logger_provider = LoggerProvider(resource=resource)
_logs.set_logger_provider(logger_provider)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)))

# Logging Instrumentation (for standard logs)
LoggingInstrumentor().instrument(set_logging_format=True)
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)

# gRPC Client Instrumentation
GrpcInstrumentorClient().instrument()

# FastAPI Instrumentation
FastAPIInstrumentor.instrument_app(app)

@app.middleware("http")
async def resilience_middleware(request: Request, call_next):
    # 1. Load Shedding Check
    if load_shedder.should_shed(request.url.path, request.method):
        LOADSHED_REJECTS.inc()
        return StreamingResponse(
            iter([b'{"detail": "System under heavy load. Please try again later."}']),
            status_code=503,
            media_type="application/json"
        )

    # 2. Rate Limiting Check
    # Identify user (from JWT if available, else IP)
    # Note: Dependencies haven't run yet, so we manually check the header/query
    user_id = None
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token") or request.query_params.get("access_token")
    
    if token:
        try:
            # Import here to avoid circular dependencies if any
            from jose import jwt
            from .auth import JWT_SECRET_KEY, ALGORITHM
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
        except Exception:
            # If token is invalid, we fallback to IP-based limiting for the request
            pass

    client_ip = request.client.host if request.client else "unknown"
    
    if user_id:
        limit_key = f"user:{user_id}"
        capacity = 100
        fill_rate = 1.66
    else:
        limit_key = f"ip:{client_ip}"
        capacity = 1000
        fill_rate = 16.6
    
    allowed, remaining, retry_after = rate_limiter.is_allowed(limit_key, capacity, fill_rate)
    
    if not allowed:
        RATELIMIT_REJECTS.inc()
        logger.warning(f"Rate limit exceeded for {limit_key}")
        return StreamingResponse(
            iter([b'{"detail": "Too Many Requests. Please slow down."}']),
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(retry_after)}
        )

    RATELIMIT_HITS.inc()
    response = await call_next(request)
    
    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(capacity)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    
    return response

from fastapi.responses import StreamingResponse

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price_cents: int

class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItem]

def grpc_retry(retries=3, delay=1):
    """Decorator to retry gRPC calls on transient errors"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_err = None
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except grpc.RpcError as e:
                    last_err = e
                    # Retry on UNAVAILABLE (often during restart/hot-reload)
                    if e.code() == grpc.StatusCode.UNAVAILABLE:
                        logger.warning(f"gRPC service unavailable (attempt {i+1}/{retries}). Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    raise
            raise last_err
        return wrapper
    return decorator

@app.get("/inventory", dependencies=[Depends(verify_jwt)])
@grpc_retry()
async def list_inventory():
    try:
        rpc_request = inventory_pb2.ListInventoryRequest()
        response = await app.state.inventory_stub.ListInventory(rpc_request)
        return {
            "inventory": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "media_id": getattr(item, 'media_id', "")
                } for item in response.items
            ]
        }
    except Exception as e:
        logger.error(f"Inventory Service gRPC call failed: {e}")
        if isinstance(e, grpc.RpcError):
             raise HTTPException(status_code=503, detail=f"Inventory Service unavailable: {e.details()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    health_status = {
        "status": "healthy",
        "version": "0.1.0",
        "gateway": "ok",
        "dependencies": {}
    }
    overall_status = True

    async def check_url(name, url):
        nonlocal overall_status
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=2.0)
                if resp.status_code == 200:
                    health_status["dependencies"][name] = resp.json()
                else:
                    health_status["dependencies"][name] = {
                        "status": "unhealthy",
                        "code": resp.status_code
                    }
                    overall_status = False
        except Exception as e:
            health_status["dependencies"][name] = {
                "status": "unreachable",
                "error": str(e)
            }
            overall_status = False

    # Check Downstream Services (using internal docker ports/hosts)
    # Auth Service is at 8002
    # Inventory Service is at 8001
    # Order Service (Go health server) is at 8081
    
    await asyncio.gather(
        check_url("auth", f"http://{os.getenv('AUTH_SERVICE_HOST', 'auth-service')}:8002/health"),
        check_url("inventory", f"http://{os.getenv('INVENTORY_SERVICE_HOST', 'inventory-service')}:8001/health"),
        check_url("order", f"http://{os.getenv('ORDER_SERVICE_HOST', 'order-service')}:8081/health")
    )

    # Check Redis
    try:
        bloom_manager.redis_client.ping()
        health_status["dependencies"]["redis"] = "healthy"
    except Exception as e:
        health_status["dependencies"]["redis"] = f"error: {str(e)}"
        overall_status = False

    if not overall_status:
        health_status["status"] = "degraded"
        # We don't raise 503 if gateway itself is OK but dependencies are degraded,
        # unless it's a critical dependency like Redis.
        # But for this task, let's keep it healthy as long as gateway can respond.
        # Actually, let's follow the previous pattern but return status codes.
        # w.WriteHeader(http.StatusServiceUnavailable) in Go style.
        # FastAPI way:
        # return JSONResponse(status_code=503, content=health_status)

    return health_status

@app.get("/")
async def root():
    return {"message": "Welcome to Order Processing API Gateway", "status": "Online"}


@app.get("/metrics/filters")
async def get_filter_metrics():
    # Fetch bloom filter metrics
    metrics_data = bloom_manager.get_metrics()
    
    # Fetch resilience metrics
    resilience_keys = [
        "metrics:ratelimit_hits",
        "metrics:ratelimit_rejects",
        "metrics:loadshed_rejects"
    ]
    vals = bloom_manager.redis_client.mget(resilience_keys)
    resilience_metrics = dict(zip([k.split(':')[-1] for k in resilience_keys], [int(v) if v else 0 for v in vals]))
    
    metrics_data.update(resilience_metrics)
    return metrics_data

@app.get("/cluster/status", dependencies=[Depends(verify_jwt)])
async def get_cluster_status():
    """Proxy Raft Cluster Status from Inventory Service"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{os.getenv('INVENTORY_SERVICE_HOST', 'inventory-service')}:8001/cluster/status", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail="Failed to fetch cluster status")
    except Exception as e:
        logger.error(f"Cluster Status fetch failed: {e}")
        raise HTTPException(status_code=503, detail=f"Inventory Service cluster status unavailable: {e}")

# Initialize load shedder with redis client for metrics
load_shedder.redis_client = bloom_manager.redis_client

@app.post("/metrics/stress")
async def set_stress(level: float):
    """Manually set the stress level for load shedding simulation (0.0 to 1.0)"""
    load_shedder.set_stress_level(level)
    SYSTEM_STRESS.set(load_shedder.stress_level)
    return {"status": "success", "stress_level": load_shedder.stress_level}

@app.post("/orders")
@grpc_retry()
async def create_order(request: CreateOrderRequest, user: dict = Depends(verify_jwt), req_obj: Request = None):
    # Use the verified user_id instead of whatever the client sent for safety
    customer_id = req_obj.state.user_id if req_obj else request.customer_id
    
    # Tier-1 Bloom Filter Check: Is the product in the catalog?
    for item in request.items:
        if not bloom_manager.is_present(item.product_id):
            logger.warning(f"Bloom Filter Reject (Tier-1): Product {item.product_id} not in catalog")
            raise HTTPException(
                status_code=400, 
                detail=f"Product {item.product_id} is invalid or not found in our catalog."
            )

    # Idempotency Check
    idempotency_key = req_obj.headers.get("Idempotency-Key") if req_obj else None
    req_hash = hashlib.sha256(request.json().encode() if hasattr(request, 'json') else json.dumps(request.dict()).encode()).hexdigest()
    
    if idempotency_key:
        redis_key = f"idempotency:api:{idempotency_key}"
        try:
            # 1. Check existing state
            cached_data = bloom_manager.redis_client.get(redis_key)
            if cached_data:
                cached_json = json.loads(cached_data)
                
                # If still processing, tell client to wait
                if cached_json.get("status") == "processing":
                    logger.warning(f"Idempotency Conflict: Key {idempotency_key} is currently processing")
                    raise HTTPException(status_code=425, detail="Order is already being processed. Please wait.")
                
                # If completed, check hash
                if cached_json.get("hash") == req_hash:
                    logger.info(f"Idempotency Hit: Returning cached response for key {idempotency_key}")
                    return cached_json.get("response")
                else:
                    logger.warning(f"Idempotency Conflict: Key {idempotency_key} used with different payload")
                    raise HTTPException(status_code=409, detail="Idempotency key conflict: different request payload for the same key.")
            
            # 2. Atomic claim: Set to 'processing' if not exists
            processing_data = {
                "status": "processing",
                "hash": req_hash,
                "timestamp": time.time()
            }
            if not bloom_manager.redis_client.set(redis_key, json.dumps(processing_data), nx=True, ex=300): # 5 min lock
                # If set failed, it was just set by someone else. Re-run check.
                cached_data = bloom_manager.redis_client.get(redis_key)
                if cached_data:
                    cached_json = json.loads(cached_data)
                    if cached_json.get("status") == "processing":
                        raise HTTPException(status_code=425, detail="Order is already being processed. Please wait.")
                    if cached_json.get("hash") == req_hash:
                        return cached_json.get("response")
                    raise HTTPException(status_code=409, detail="Idempotency key conflict.")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking idempotency: {e}")
            raise HTTPException(status_code=503, detail="Idempotency check failed. Service unavailable.")

    try:
        # Map items
        rpc_items = [
            order_pb2.OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                price_cents=item.price_cents
            ) for item in request.items
        ]
        
        rpc_request = order_pb2.CreateOrderRequest(
            customer_id=str(customer_id),
            items=rpc_items
        )
        
        response = await app.state.order_stub.CreateOrder(rpc_request)
        result = {
            "order_id": response.order_id,
            "status": order_pb2.OrderStatus.Name(response.status)
        }

        # Store in Redis if idempotency key was provided
        if idempotency_key:
            try:
                idempotency_data = {
                    "status": "completed",
                    "hash": req_hash,
                    "response": result
                }
                bloom_manager.redis_client.setex(
                    redis_key,
                    86400, # 24h TTL
                    json.dumps(idempotency_data)
                )
            except Exception as e:
                logger.error(f"Error storing idempotency data: {e}")

        return result
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            raise HTTPException(status_code=400, detail=f"Order rejected: {e.details()}")
        raise HTTPException(status_code=503, detail=f"Order Service error: {e.details()}")

@app.get("/orders")
@grpc_retry()
async def list_orders(customer_id: Optional[str] = None, user: dict = Depends(verify_jwt), req_obj: Request = None):
    # If no customer_id provided, filter by the logged-in user
    id_to_query = customer_id or req_obj.state.user_id
    
    try:
        rpc_request = order_pb2.ListOrdersRequest(customer_id=str(id_to_query))
        response = await app.state.order_stub.ListOrders(rpc_request)
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
                            "price_cents": item.price_cents
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
async def stream_order_updates(
    customer_id: Optional[str] = None, 
    token: Optional[str] = None,
    user: dict = Depends(verify_jwt), 
    req_obj: Request = None
):
    """
    Server-Sent Events (SSE) endpoint for real-time order status updates.
    """
    id_to_stream = customer_id or req_obj.state.user_id
    return StreamingResponse(
        order_status_streamer(str(id_to_stream), app.state.stream_stub),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for Nginx
        }
    )

@app.get("/orders/{order_id}", dependencies=[Depends(verify_jwt)])
@grpc_retry()
async def get_order(order_id: str):
    try:
        rpc_request = order_pb2.GetOrderRequest(order_id=order_id)
        response = await app.state.order_stub.GetOrder(rpc_request)
        return {
            "order_id": response.order_id,
            "customer_id": response.customer_id,
            "status": order_pb2.OrderStatus.Name(response.status),
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price_cents": item.price_cents
                } for item in response.items
            ],
            "media_ids": list(response.media_ids) if hasattr(response, "media_ids") else []
        }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=503, detail=f"Order Service unavailable: {e.details()}")

class MediaUploadURLRequest(BaseModel):
    entity_type: str
    entity_id: str
    file_name: str
    content_type: str

@app.post("/media/upload-url", dependencies=[Depends(verify_jwt)])
async def get_media_upload_url(request: MediaUploadURLRequest):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"http://{os.getenv('MEDIA_SERVICE_HOST', 'media-service')}:8008/media/upload-url",
                json=request.dict(),
                timeout=5.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except Exception as e:
            logger.error(f"Media Service call failed: {e}")
            raise HTTPException(status_code=503, detail=f"Media Service unavailable: {e}")

@app.get("/media/{media_id}/view-url", dependencies=[Depends(verify_jwt)])
async def get_media_view_url(media_id: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"http://{os.getenv('MEDIA_SERVICE_HOST', 'media-service')}:8008/media/{media_id}/view-url",
                timeout=5.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except Exception as e:
            logger.error(f"Media Service call failed: {e}")
            raise HTTPException(status_code=503, detail=f"Media Service unavailable: {e}")

@app.post("/media/{media_id}/confirm-upload", dependencies=[Depends(verify_jwt)])
async def confirm_media_upload(media_id: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"http://{os.getenv('MEDIA_SERVICE_HOST', 'media-service')}:8008/media/{media_id}/confirm-upload",
                timeout=5.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except Exception as e:
            logger.error(f"Media Service call failed: {e}")
            raise HTTPException(status_code=503, detail=f"Media Service unavailable: {e}")

@app.get("/me")
async def get_me(user: dict = Depends(verify_jwt), req_obj: Request = None):
    return {
        "user_id": req_obj.state.user_id,
        "username": req_obj.state.username
    }

@app.get("/orders/search")
async def search_orders(q: str):
    """
    Search orders in Elasticsearch
    """
    try:
        body = {
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["order_id", "customer_id", "status", "message"]
                }
            }
        }
        resp = await app.state.es_client.search(index="order_analytics", body=body)
        return {
            "total": resp["hits"]["total"]["value"],
            "orders": [hit["_source"] for hit in resp["hits"]["hits"]]
        }
    except Exception as e:
        logger.error(f"Elasticsearch search failed: {e}")
        # If index doesn't exist yet, return empty
        return {"total": 0, "orders": [], "error": str(e)}

@app.get("/analytics/flow")
async def get_analytics_flow():
    """
    Returns metadata about the streaming flow for visualization
    """
    return {
        "nodes": [
            {"id": "kafka", "type": "input", "data": {"label": "Kafka (order-events)"}, "position": {"x": 0, "y": 0}},
            {"id": "flink", "type": "default", "data": {"label": "Flink (Analytics Pipeline)"}, "position": {"x": 250, "y": 0}},
            {"id": "elasticsearch", "type": "output", "data": {"label": "Elasticsearch"}, "position": {"x": 500, "y": -50}},
            {"id": "clickhouse", "type": "output", "data": {"label": "ClickHouse"}, "position": {"x": 500, "y": 50}}
        ],
        "edges": [
            {"id": "e-kf", "source": "kafka", "target": "flink", "animated": True},
            {"id": "e-fe", "source": "flink", "target": "elasticsearch", "label": "Sink"},
            {"id": "e-fc", "source": "flink", "target": "clickhouse", "label": "Sink"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
