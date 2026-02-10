import asyncio
import logging
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
from .database import init_db, get_db, async_session
from .models import InventoryItem
from .bloom_filter import filter_manager

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
    async with async_session() as session:
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
                async with async_session() as session:
                    items = await crud.get_all_inventory(session)
                    filter_manager.sync_from_db(items)
                logger.info("Bloom/Cuckoo filters successfully populated from database.")
            except Exception as e:
                logger.error(f"Seeding failed: {e}")
            finally:
                filter_manager.redis_client.delete(lock_key)
        else:
            logger.info("Another instance is already seeding filters. Skipping.")

    # Run seeding in background to not block app startup
    asyncio.create_task(background_seeding())

    # Periodic Sync Task (Industry Practice)
    async def periodic_sync():
        while True:
            await asyncio.sleep(600) # Sync every 10 mins
            await background_seeding()
    
    asyncio.create_task(periodic_sync())
    
    kafka_brokers = os.getenv("KAFKA_BROKERS", "kafka:29092")
    app.state.kafka = KafkaManager(kafka_brokers, "order-events", "order-events")
    await app.state.kafka.start()
    
    # Start gRPC server in the background
    server = grpc.aio.server()
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    listen_addr = "[::]:50052"
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting gRPC server on {listen_addr}")
    await server.start()
    
    yield
    
    # Shutdown logic
    logger.info("Stopping gRPC server...")
    await server.stop(0)
    await app.state.kafka.stop()
    # Shutdown OpenTelemetry providers
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger_provider.shutdown()


# FastAPI Setup
app = FastAPI(title="Inventory Service API", version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health():
    health_status = {"status": "ok", "checks": {}}
    overall_status = True

    # Check Database
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "connected"
    except Exception as e:
        logger.error(f"DB Health check failed: {e}")
        health_status["checks"]["database"] = f"failed: {str(e)}"
        overall_status = False

    # Check Redis
    try:
        filter_manager.redis_client.ping()
        health_status["checks"]["redis"] = "connected"
    except Exception as e:
        logger.error(f"Redis Health check failed: {e}")
        health_status["checks"]["redis"] = f"failed: {str(e)}"
        overall_status = False

    if not overall_status:
        health_status["status"] = "error"
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@app.get("/inventory")
async def list_inventory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryItem))
    items = result.scalars().all()
    return items

from . import crud

# gRPC Servicer Implementation
class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    async def CheckStock(self, request, context):
        async with async_session() as session:
            item = await crud.get_inventory_item(session, request.product_id)
            quantity = item.quantity if item else 0
            return inventory_pb2.CheckStockResponse(product_id=request.product_id, quantity=quantity)

    async def ReserveStock(self, request, context):
        # Tier-2 Bloom Filter Check: Is the product likely in stock?
        for item in request.items:
            if not filter_manager.is_in_stock(item.product_id):
                logger.info(f"Bloom Filter Reject (Tier-2): Product {item.product_id} likely out of stock")
                return inventory_pb2.ReserveStockResponse(
                    success=False, 
                    message=f"Product {item.product_id} is likely out of stock (Tier-2 check)"
                )

        async with async_session() as session:
            try:
                success, message = await crud.reserve_stock_atomic(session, request.order_id, request.items)
                return inventory_pb2.ReserveStockResponse(success=success, message=message)
            except Exception as e:
                logger.error(f"Error during stock reservation: {e}")
                await session.rollback()
                return inventory_pb2.ReserveStockResponse(success=False, message=str(e))

    async def ReleaseStock(self, request, context):
        async with async_session() as session:
            try:
                await crud.release_stock_atomic(session, request.order_id, request.items)
                return inventory_pb2.ReleaseStockResponse(success=True)
            except Exception as e:
                logger.error(f"Error during stock release: {e}")
                await session.rollback()
                return inventory_pb2.ReleaseStockResponse(success=False)

    async def UpdateStock(self, request, context):
        async with async_session() as session:
            try:
                db_item = await crud.update_stock_level(session, request.product_id, request.quantity_change)
                return inventory_pb2.UpdateStockResponse(
                    product_id=db_item.product_id, 
                    new_quantity=db_item.quantity
                )
            except Exception as e:
                await session.rollback()
                context.abort(grpc.StatusCode.INTERNAL, str(e))
