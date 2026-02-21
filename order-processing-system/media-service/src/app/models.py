from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from .database import Base

class MediaMetadata(Base):
    __tablename__ = "media_metadata"

    media_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False) # e.g., 'inventory', 'order'
    entity_id = Column(String(100), nullable=False)
    bucket_name = Column(String(100), nullable=False)
    object_key = Column(String(500), nullable=False)
    content_hash = Column(String(64), nullable=True) # SHA-256
    content_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
