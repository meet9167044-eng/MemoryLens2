import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScreenshotUploadResponse(BaseModel):
    """Returned after a successful screenshot upload."""
    screenshot_id: uuid.UUID
    status: str
    file_path: str
    original_filename: str
    file_size_bytes: int
    file_hash: str
    message: str

    class Config:
        from_attributes = True


class ScreenshotStatusResponse(BaseModel):
    """Returned when querying a screenshot's current status."""
    screenshot_id: uuid.UUID
    status: str
    stage: Optional[str] = Field(default=None, description="Current pipeline stage if processing")
    original_filename: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: str
    detail: str
