import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

import os

# Use standard JSON if running with SQLite in tests, otherwise JSONB for Postgres
JSON_VARIANT = JSON if os.environ.get("TESTING", "") == "1" else JSONB

# Try to import pgvector support (Phase C)
try:
    from pgvector.sqlalchemy import Vector as PgVector
    _HAS_PGVECTOR = True
except ImportError:
    PgVector = None
    _HAS_PGVECTOR = False

EMBEDDING_DIM = 768   # all-mpnet-base-v2 local model dimension (matches Gemini)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    screenshot_id = Column(UUID(as_uuid=True), ForeignKey("screenshots.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(512), nullable=True)
    summary = Column(Text, nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    content_type = Column(String(128), nullable=True)
    app_detected = Column(String(256), nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    domain = Column(String(256), nullable=True)
    tags = Column(JSON_VARIANT, nullable=True, default=list)
    confidence_score = Column(Float, nullable=True)
    # Phase C: real pgvector column - stores 768-dim vectors
    embedding = Column(PgVector(EMBEDDING_DIM), nullable=True) if _HAS_PGVECTOR else Column(Text, nullable=True)
    # Legacy placeholder kept until all rows are migrated
    embedding_placeholder = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    screenshot = relationship("Screenshot", back_populates="memories")
    entities = relationship("Entity", back_populates="memory", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Memory id={self.id} title={self.title!r} app={self.app_detected!r}>"
