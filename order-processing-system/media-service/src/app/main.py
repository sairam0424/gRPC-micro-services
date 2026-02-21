from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
import os
import logging
from contextlib import asynccontextmanager

# OpenTelemetry
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
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from .database import get_db, init_db
from .models import MediaMetadata
from .minio_manager import minio_manager
from .kafka_manager import kafka_manager

# OpenTelemetry Setup
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
resource = Resource.create({"service.name": "media-service"})

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    FastAPIInstrumentor.instrument_app(app)
    await init_db()
    await kafka_manager.start()
    yield
    # Shutdown logic
    await kafka_manager.stop()

app = FastAPI(title="Media Service", lifespan=lifespan)

class UploadURLRequest(BaseModel):
    entity_type: str
    entity_id: str
    filename: str
    content_type: str = "application/octet-stream"

class UploadURLResponse(BaseModel):
    media_id: str
    upload_url: str
    object_key: str

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/media/upload-url", response_model=UploadURLResponse)
async def get_upload_url(
    request: UploadURLRequest, 
    db: AsyncSession = Depends(get_db)
):
    bucket_map = {
        "inventory": "inventory-images",
        "order": "order-attachments"
    }
    bucket_name = bucket_map.get(request.entity_type)
    if not bucket_name:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {request.entity_type}")

    media_id = str(uuid.uuid4())
    object_key = f"{request.entity_type}/{request.entity_id}/{media_id}_{request.filename}"

    try:
        upload_url = minio_manager.generate_upload_url(bucket_name, object_key)
        
        new_media = MediaMetadata(
            media_id=uuid.UUID(media_id),
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            bucket_name=bucket_name,
            object_key=object_key,
            content_type=request.content_type
        )
        db.add(new_media)
        await db.commit()

        return UploadURLResponse(
            media_id=media_id,
            upload_url=upload_url,
            object_key=object_key
        )
    except Exception as e:
        logger.error(f"Error creating upload URL: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/media/{media_id}/view-url")
async def get_view_url(media_id: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(MediaMetadata).where(MediaMetadata.media_id == uuid.UUID(media_id))
        result = await db.execute(stmt)
        media = result.scalars().first()

        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        view_url = minio_manager.generate_view_url(media.bucket_name, media.object_key)
        return {"media_id": media_id, "view_url": view_url}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        logger.error(f"Error fetching view URL: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/media/{media_id}/confirm-upload")
async def confirm_upload(
    media_id: str, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(MediaMetadata).where(MediaMetadata.media_id == uuid.UUID(media_id))
        result = await db.execute(stmt)
        media = result.scalars().first()

        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        event = {
            "event_type": "media.uploaded",
            "media_id": str(media.media_id),
            "entity_type": media.entity_type,
            "entity_id": media.entity_id,
            "object_key": media.object_key,
            "bucket": media.bucket_name
        }
        background_tasks.add_task(kafka_manager.send_event, "media.events", event)

        return {"status": "confirmed", "media_id": media_id}
    except Exception as e:
        logger.error(f"Error confirming upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
