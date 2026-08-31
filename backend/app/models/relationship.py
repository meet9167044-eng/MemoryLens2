"""
Phase 9 - Relationship Model
Stores scored relationships between Memory records.
"""
import uuid
import enum
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, UniqueConstraint, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class RelationshipType(str, enum.Enum):
    SHARED_ENTITY = "shared_entity"   # both memories mention the same entity (e.g. "CUDA")
    SHARED_TAG    = "shared_tag"      # both memories share a tag label
    SEMANTIC      = "semantic"        # high cosine similarity of embeddings
    TEMPORAL      = "temporal"        # captured within a short time window
    DOMAIN        = "domain"          # captured on the same website/domain


class Relationship(Base):
    """
    Undirected relationship between two Memories.

    We enforce source_id < target_id at the application level so we never
    create duplicate (A→B) and (B→A) rows for the same pair.
    """
    __tablename__ = "relationships"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_id  = Column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    target_id  = Column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    rel_type   = Column(Enum(
                        RelationshipType,
                        name="relationship_type",
                        values_callable=lambda enum_type: [item.value for item in enum_type],
                    ),
                        nullable=False, default=RelationshipType.SHARED_ENTITY)
    score      = Column(Float, nullable=False, default=0.0)   # 0.0 – 1.0
    explanation = Column(String(512), nullable=True)           # human-readable reason

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Prevent duplicate undirected rows (same pair + same type)
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "rel_type", name="uq_relationship_pair_type"),
    )

    source = relationship("Memory", foreign_keys=[source_id])
    target = relationship("Memory", foreign_keys=[target_id])

    def __repr__(self):
        return (
            f"<Relationship {self.rel_type} "
            f"source={self.source_id} target={self.target_id} score={self.score:.2f}>"
        )
