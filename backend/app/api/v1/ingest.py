"""
POST /api/v1/ingest  — Screenshot Ingestion Endpoint (Phase 3 / Phase 10)

Accepts a multipart/form-data image upload, validates it,
saves it to disk via StorageProvider, and creates a Screenshot
record in the database with status=PENDING.

Phase 10 addition: after the DB commit, fires run_pipeline() in a
daemon thread so the API returns 201 immediately while all processing
(OCR, extraction, embeddings, relationships) runs in the background.
"""
import io
import threading

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
import os
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.jobs.pipeline import run_pipeline
from app.jobs.queue import pipeline_queue
from app.models.screenshot import Screenshot, ScreenshotStatus
from app.schemas.ingest import ErrorResponse, ScreenshotUploadResponse, ScreenshotStatusResponse
from app.services.storage import storage

router = APIRouter(prefix="/api/v1", tags=["ingestion"])

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # bytes
ALLOWED_MIME = set(settings.ALLOWED_MIME_TYPES)

import logging as _logging
_log = _logging.getLogger(__name__)


def _run_pipeline_safe(screenshot_id) -> None:
    """Fallback thread target (used if queue is full)."""
    try:
        run_pipeline(screenshot_id=screenshot_id)
    except Exception as exc:  # pragma: no cover
        _log.error("Unhandled pipeline error for %s: %s", screenshot_id, exc, exc_info=True)


def _validate_image(data: bytes, content_type: str, filename: str) -> None:
    """
    Validates the uploaded file on three levels:
    1. MIME type whitelist
    2. File extension whitelist
    3. Actual pixel-level decodability (Pillow verify)

    Raises HTTPException(400) if any check fails.
    """
    # 1. MIME type check
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{content_type}'. Allowed: {sorted(ALLOWED_MIME)}",
        )

    # 2. Extension check
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    import os
    ext = os.path.splitext(filename or "")[-1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(allowed_exts)}",
        )

    # 3. Decodability — try to open with Pillow to catch corrupted files
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()  # raises if file is corrupted
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is corrupted or not a valid image: {exc}",
        )


@router.post(
    "/ingest",
    response_model=ScreenshotUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a screenshot for ingestion",
    description=(
        "Accepts a PNG/JPEG/WEBP screenshot, validates it, saves it to disk, "
        "and creates a PENDING Screenshot record in the database. "
        "OCR and AI processing happen asynchronously in later pipeline stages."
    ),
)
async def ingest_screenshot(
    file: UploadFile = File(..., description="The screenshot image file to ingest"),
    db: Session = Depends(get_db),
) -> ScreenshotUploadResponse:
    # ── 1. Read file bytes ─────────────────────────────────────────────────────
    data = await file.read()

    # ── 2. Size check ──────────────────────────────────────────────────────────
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max allowed: {settings.MAX_FILE_SIZE_MB} MB",
        )

    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── 3. Validate MIME, extension, and decodability ─────────────────────────
    _validate_image(data, file.content_type or "", file.filename or "upload.png")

    # ── 4. Deduplication check — compute hash BEFORE saving to disk ───────────
    file_hash = storage.compute_hash(data)
    existing = db.query(Screenshot).filter(Screenshot.file_hash == file_hash).first()
    if existing:
        _log.info("Duplicate upload detected: hash %s already exists as screenshot %s", file_hash, existing.id)
        return ScreenshotUploadResponse(
            screenshot_id=existing.id,
            status=existing.status.value,
            file_path=existing.file_path,
            original_filename=existing.original_filename or file.filename or "upload.png",
            file_size_bytes=existing.file_size_bytes or len(data),
            file_hash=file_hash,
            message="Duplicate detected — this screenshot was already ingested. Returning existing record.",
        )

    # ── 5. Save to disk via StorageProvider ────────────────────────────────────
    try:
        storage_meta = storage.save(data, file.filename or "upload.png")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File write error: {exc}",
        )

    # ── 6. Persist Screenshot record in DB ────────────────────────────────────
    screenshot = Screenshot(
        file_path=storage_meta["file_path"],
        original_filename=file.filename,
        file_size_bytes=storage_meta["file_size_bytes"],    # now Integer
        file_hash=storage_meta["file_hash"],                # persisted for future dedup checks
        mime_type=file.content_type,
        status=ScreenshotStatus.PENDING,
    )
    db.add(screenshot)
    db.commit()
    db.refresh(screenshot)

    # ── 7. Submit to pipeline queue (Phase F) ───────────────────────────
    _screenshot_id = screenshot.id
    accepted = pipeline_queue.enqueue(_screenshot_id)
    if not accepted:
        # Queue full — fall back to raw thread
        _log.warning("Queue full, falling back to raw thread for screenshot %s", _screenshot_id)
        threading.Thread(
            target=_run_pipeline_safe,
            args=(_screenshot_id,),
            daemon=True,
            name=f"pipeline-fallback-{_screenshot_id}",
        ).start()

    return ScreenshotUploadResponse(
        screenshot_id=screenshot.id,
        status=screenshot.status.value,
        file_path=storage_meta["file_path"],
        original_filename=file.filename or "upload.png",
        file_size_bytes=storage_meta["file_size_bytes"],
        file_hash=storage_meta["file_hash"],
        message="Screenshot ingested successfully. Processing pipeline started.",
    )


@router.get(
    "/ingest/{screenshot_id}",
    response_model=ScreenshotStatusResponse,
    summary="Get ingestion status of a screenshot",
)
def get_screenshot_status(screenshot_id: str, db: Session = Depends(get_db)):
    """Returns the current status of an uploaded screenshot."""
    import uuid as uuid_mod
    try:
        uid = uuid_mod.UUID(screenshot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid screenshot ID format.")

    ss = db.query(Screenshot).filter(Screenshot.id == uid).first()
    if not ss:
        raise HTTPException(status_code=404, detail="Screenshot not found.")

    return ScreenshotStatusResponse(
        screenshot_id=ss.id,
        status=ss.status.value,
        original_filename=ss.original_filename,
        created_at=ss.created_at,
    )


@router.get(
    "/screenshots/{screenshot_id}/image",
    summary="Get screenshot image",
    description="Returns the raw image file for the screenshot."
)
def get_screenshot_image(screenshot_id: str, db: Session = Depends(get_db)):
    """Serves the actual image file bytes."""
    import uuid as uuid_mod
    try:
        uid = uuid_mod.UUID(screenshot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid screenshot ID format.")

    ss = db.query(Screenshot).filter(Screenshot.id == uid).first()
    if not ss:
        raise HTTPException(status_code=404, detail="Screenshot not found.")
        
    if not ss.file_path or not os.path.exists(ss.file_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk.")
        
    return FileResponse(ss.file_path, media_type=ss.mime_type or "image/png")


@router.post(
    "/ingest/bulk",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bulk import multiple screenshots",
    description=(
        "Accepts up to 50 screenshot files in a single request. "
        "Each file is validated, deduplicated, saved, and queued for pipeline processing. "
        "Returns a summary of accepted and rejected files."
    ),
)
async def bulk_ingest_screenshots(
    files: list[UploadFile] = File(..., description="Up to 50 screenshot files"),
    db: Session = Depends(get_db),
):
    """Ingest multiple screenshots in one call. Designed for bulk imports and folder sync."""
    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many files. Max 50 per bulk request.",
        )

    accepted = []
    rejected = []
    duplicates = []

    for upload in files:
        filename = upload.filename or "upload.png"
        try:
            data = await upload.read()

            if len(data) == 0:
                rejected.append({"filename": filename, "reason": "Empty file"})
                continue

            if len(data) > MAX_FILE_SIZE:
                rejected.append({"filename": filename, "reason": f"Exceeds {settings.MAX_FILE_SIZE_MB} MB limit"})
                continue

            try:
                _validate_image(data, upload.content_type or "", filename)
            except HTTPException as val_err:
                rejected.append({"filename": filename, "reason": val_err.detail})
                continue

            # Deduplication
            file_hash = storage.compute_hash(data)
            existing = db.query(Screenshot).filter(Screenshot.file_hash == file_hash).first()
            if existing:
                duplicates.append({"filename": filename, "screenshot_id": str(existing.id)})
                continue

            # Save and create record
            meta = storage.save(data, filename)
            screenshot = Screenshot(
                file_path=meta["file_path"],
                original_filename=filename,
                file_size_bytes=meta["file_size_bytes"],
                file_hash=meta["file_hash"],
                mime_type=upload.content_type,
                status=ScreenshotStatus.PENDING,
            )
            db.add(screenshot)
            db.commit()
            db.refresh(screenshot)

            sid = screenshot.id
            if not pipeline_queue.enqueue(sid, priority=7):  # bulk = lower priority
                threading.Thread(
                    target=_run_pipeline_safe,
                    args=(sid,),
                    daemon=True,
                    name=f"bulk-fallback-{sid}",
                ).start()

            accepted.append({"filename": filename, "screenshot_id": str(sid)})

        except Exception as exc:
            _log.error("Bulk ingest error for %s: %s", filename, exc, exc_info=True)
            rejected.append({"filename": filename, "reason": "Internal error"})

    return {
        "accepted": accepted,
        "rejected": rejected,
        "duplicates": duplicates,
        "summary": {
            "total": len(files),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "duplicate_count": len(duplicates),
        },
    }
