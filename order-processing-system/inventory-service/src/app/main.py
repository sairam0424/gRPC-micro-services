import asyncio
import logging
import os
import sys

# Add src directory to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
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
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer, GrpcInstrumentorClient
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from concurrent import futures
import grpc
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text

# Ensure generated code is in the path
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
sys.path.append(GENERATED_DIR)

from inventory.v1 import inventory_pb2, inventory_pb2_grpc
from app.database import init_db, get_db, writer_session, reader_sessions
from app.models import InventoryItem
from app.bloom_filter import filter_manager
from app.cache import cache_manager
from app.consensus import consensus_manager

from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenTelemetry Setup
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
resource = Resource.create({"service.name": "inventory-service"})

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

# Logging Instrumentation
LoggingInstrumentor().instrument(set_logging_format=True)
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)

# gRPC Instrumentation
GrpcInstrumentorServer().instrument()
GrpcInstrumentorClient().instrument()

# Seed initial data
async def seed_data():
    async with writer_session() as session:
        result = await session.execute(select(InventoryItem).limit(1))
        if not result.scalar():
            logger.info("Seeding initial inventory data...")
            items = [
                InventoryItem(product_id="PROD-001", name="Laptop", quantity=10),
                InventoryItem(product_id="PROD-002", name="Mouse", quantity=50),
                InventoryItem(product_id="PROD-003", name="Keyboard", quantity=25),
            ]
            session.add_all(items)
            await session.commit()

from .kafka_manager import KafkaManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    FastAPIInstrumentor.instrument_app(app)
    await init_db()

    # Initialize Bloom/Cuckoo Filters structure
    filter_manager.init_filters()
    
    # Background Seeding Task
    async def background_seeding():
        lock_key = "lock:filter_seeding"
        # Try to acquire lock for 30 seconds
        if filter_manager.redis_client.set(lock_key, "locked", nx=True, ex=60):
            try:
                logger.info("Acquired seeding lock. Starting Bloom/Cuckoo filter population...")
                async with writer_session() as session:
                    # We need to import crud here or ensure it's available
                    from . import crud
                    items = await crud.get_all_inventory(session)
                    filter_manager.sync_from_db(items)
                    
                    # Asynchronously warm the cache from replica
                    for item in items:
                        cache_manager.set_stock(item.product_id, item.quantity)
                        
                logger.info("Bloom/Cuckoo filters and Cache successfully populated from REPLICA.")
            except Exception as e:
                logger.error(f"Seeding failed: {e}")
            finally:
                filter_manager.redis_client.delete(lock_key)
        else:
            logger.info("Another instance is already seeding filters. Skipping.")

    # Run seeding in background to not block app startup
    asyncio.create_task(background_seeding())

    # Cache Warming Task (Industry Practice)
    async def cache_warming():
        logger.info("Starting industry-standard Cache Warming pipeline from REPLICA...")
        async with writer_session() as session:
            from . import crud
            # Warm cache with Top 100 items (or all for this demo)
            items = await crud.get_all_inventory(session)
            if items:
                for item in items:
                    cache_manager.set_stock(item.product_id, item.quantity)
                logger.info(f"Cache Warming complete via Replica. {len(items)} items warmed.")
            else:
                logger.info("No items found to warm cache.")

    asyncio.create_task(cache_warming())

    # Periodic Sync Task (Industry Practice)
    async def periodic_sync():
        while True:
            await asyncio.sleep(600)  # Sync every 10 mins
            await background_seeding()
    
    asyncio.create_task(periodic_sync())
    
    kafka_brokers = os.getenv("KAFKA_BROKERS", "kafka:29092")
    schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    
    # Raft Consensus Registration
    await consensus_manager.register_node()
    
    app.state.kafka = KafkaManager(
        kafka_brokers, 
        "data.order-events", 
        "data.inventory-events",
        schema_registry_url,
        topic_dlq="data.inventory.dlq"
    )
    # Start Kafka consumer in a background thread (it's a blocking synchronous loop)
    kafka_thread = threading.Thread(target=app.state.kafka.start, daemon=True)
    kafka_thread.start()
    logger.info("Kafka Manager consumer started in background thread")
    
    # Start gRPC server in a background task (non-blocking)
    async def run_grpc_server():
        server = grpc.aio.server()
        inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
        listen_addr = "[::]:50052"
        server.add_insecure_port(listen_addr)
        logger.info(f"Starting gRPC server on {listen_addr}")
        await server.start()
        app.state.grpc_server = server
        # Keep the server running
        await server.wait_for_termination()
    
    # Start gRPC server as background task
    asyncio.create_task(run_grpc_server())

    # Start Saga Manager for Kafka orchestration
    from .saga_manager import SagaManager
    app.state.saga = SagaManager(
        kafka_brokers,
        "ctrl.saga-commands",
        "ctrl.saga-events"
    )
    saga_thread = threading.Thread(target=app.state.saga.start, daemon=True)
    saga_thread.start()
    logger.info("Saga Manager (Inventory) started in background thread")
    
    yield
    
    # Shutdown logic
    logger.info("Stopping gRPC server...")
    if hasattr(app.state, 'grpc_server'):
        await app.state.grpc_server.stop(0)
    
    if hasattr(app.state, 'kafka'):
        app.state.kafka.stop()
    
    if hasattr(app.state, 'saga'):
        app.state.saga.stop()

    # Shutdown OpenTelemetry providers
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger_provider.shutdown()


# FastAPI Setup
app = FastAPI(title="Inventory Service API", version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health():
    health_status = {
        "status": "healthy",
        "version": "0.1.0",
        "checks": {
            "database": "unknown",
            "redis": "unknown",
            "kafka": "unknown"
        }
    }
    overall_status = "healthy"

    # Check Database
    try:
        async with writer_session() as session:
            await session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "connected"
    except Exception as e:
        logger.error(f"DB Health check failed: {e}")
        health_status["checks"]["database"] = f"failed: {str(e)}"
        overall_status = "unhealthy"

    # Check Redis
    try:
        filter_manager.redis_client.ping()
        health_status["checks"]["redis"] = "connected"
    except Exception as e:
        logger.error(f"Redis Health check failed: {e}")
        health_status["checks"]["redis"] = f"failed: {str(e)}"
        overall_status = "unhealthy"

    # Check Kafka
    if hasattr(app.state, "kafka"):
        if app.state.kafka.is_healthy():
            health_status["checks"]["kafka"] = "connected"
        else:
            health_status["checks"]["kafka"] = "connecting"
            # Don't mark as unhealthy yet if it's just connecting during startup
            if overall_status == "healthy":
                overall_status = "starting"
    else:
        health_status["checks"]["kafka"] = "not_initialized"
        overall_status = "unhealthy"

    health_status["status"] = overall_status
    
    if overall_status == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@app.get("/cluster/status")
async def get_cluster_status():
    """Get the current status of the Raft cluster (App + DB)"""
    return {
        "leader": consensus_manager.get_leader(),
        "is_leader": consensus_manager.is_leader,
        "nodes": consensus_manager.get_all_nodes(),
        "db_cluster": consensus_manager.get_db_cluster_status(),
        "current_node_id": consensus_manager.node_id
    }

@app.get("/inventory")
async def list_inventory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryItem))
    items = result.scalars().all()
    return items

from . import crud

# gRPC Servicer Implementation
class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    async def CheckStock(self, request, context):
        # 1. Try Cache
        cached_qty = cache_manager.get_stock(request.product_id)
        if cached_qty is not None:
            return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=cached_qty)

        # 2. Cache Miss: Use Single Flight to prevent Cache Stampede
        async with cache_manager.single_flight(request.product_id):
            # Re-check cache after acquiring single_flight in case another request filled it
            cached_qty = cache_manager.get_stock(request.product_id)
            if cached_qty is not None:
                return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=cached_qty)

            # Route eventual consistency read to REPLICA
            try:
                async with writer_session() as session:
                    item = await crud.get_inventory_item(session, request.product_id)
                    quantity = item.quantity if item else 0
                    
                    # 3. Populate Cache
                    cache_manager.set_stock(request.product_id, quantity)
                    
                    return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=quantity)
            except Exception as e:
                logger.error(f"Error in CheckStock: {e}", exc_info=True)
                await context.abort(grpc.StatusCode.INTERNAL, f"Database error for {request.product_id}: {str(e)}")

    async def ReserveStock(self, request, context):
        # Tier-2 Bloom Filter Check: Is the product likely in stock?
        for item in request.items:
            # 1. Negative Check (Bloom Filter)
            if not filter_manager.is_in_stock(item.product_id):
                logger.info(f"Bloom Filter Reject (Tier-2): Product {item.product_id} likely out of stock")
                return inventory_pb2.ReserveStockResponse(
                    success=False, 
                    message=f"Product {item.product_id} is likely out of stock (Tier-2 check)"
                )
            
            # 2. Fast Cache Check
            cached_qty = cache_manager.get_stock(item.product_id)
            if cached_qty is not None and cached_qty < item.quantity:
                logger.info(f"Cache Reject: Product {item.product_id} has insufficient stock ({cached_qty} < {item.quantity})")
                return inventory_pb2.ReserveStockResponse(
                    success=False,
                    message=f"Insufficient stock for {item.product_id} (cached check)"
                )

        # Route strong consistency reservation to LEADER
        async with writer_session() as session:
            try:
                success, message, reserved_items = await crud.reserve_stock_atomic(session, request.order_id, request.items)
                if success:
                    # Publish inventory update events for each item
                    for db_item, _ in reserved_items:
                        await app.state.kafka.publish_inventory_update(db_item.product_id, db_item.quantity)
                return inventory_pb2.ReserveStockResponse(success=success, message=message)
            except Exception as e:
                logger.error(f"Error during stock reservation: {e}")
                await session.rollback()
                return inventory_pb2.ReserveStockResponse(success=False, message=str(e))

    async def ReleaseStock(self, request, context):
        async with writer_session() as session:
            try:
                await crud.release_stock_atomic(session, request.order_id, request.items)
                # For release, we'd need to fetch current quantities to be precise, 
                # or just let the downstream sync happen. 
                # Better: In a real system release_stock_atomic would return updated items.
                # For this demo, let's just trigger a re-fetch and publish for each item.
                for item in request.items:
                    db_item = await crud.get_inventory_item(session, item.product_id)
                    if db_item:
                        await app.state.kafka.publish_inventory_update(db_item.product_id, db_item.quantity)
                return inventory_pb2.ReleaseStockResponse(success=True)
            except Exception as e:
                logger.error(f"Error during stock release: {e}")
                await session.rollback()
                return inventory_pb2.ReleaseStockResponse(success=False)

    async def UpdateStock(self, request, context):
        async with writer_session() as session:
            try:
                db_item = await crud.update_stock_level(session, request.product_id, request.quantity_change)
                # Always publish update event
                await app.state.kafka.publish_inventory_update(db_item.product_id, db_item.quantity)
                return inventory_pb2.UpdateStockResponse(
                    product_id=db_item.product_id, 
                    new_quantity=db_item.quantity
                )
            except Exception as e:
                logger.error(f"Error in UpdateStock: {e}", exc_info=True)
                await session.rollback()
                await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def ListInventory(self, request, context):
        # Use resilient database routing
        try:
            async with get_db() as session:
                try:
                    items = await crud.get_all_inventory(session)
                    return inventory_pb2.ListInventoryResponse(
                        items=[
                            inventory_pb2.InventoryItem(
                                product_id=item.product_id,
                                quantity=item.quantity
                            ) for item in items
                        ]
                    )
                except Exception as e:
                    logger.error(f"CRUD error in ListInventory: {e}", exc_info=True)
                    await context.abort(grpc.StatusCode.INTERNAL, str(e))
        except Exception as e:
            logger.error(f"Session error in ListInventory: {e}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, f"Failed to acquire database session: {str(e)}")
