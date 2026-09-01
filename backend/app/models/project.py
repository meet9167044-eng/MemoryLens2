import uuid
from sqlalchemy import Column, String, Float, Table, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

memory_projects = Table(
    "memory_projects",
    Base.metadata,
    Column("memory_id", UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
)

class Project(Base):
    """
    Phase K: First-class Project node.
    Automatically created via project_detector.py based on domain/tag/entity overlap.
    """
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)
    color = Column(String(50), nullable=True)
    confidence = Column(Float, default=1.0)

    memories = relationship("Memory", secondary=memory_projects, back_populates="projects")

    def __repr__(self):
        return f"<Project id={self.id} name={self.name!r}>"
