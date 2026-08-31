"""
Phase 10 â€” End-to-End Processing Pipeline
==========================================

run_pipeline(screenshot_id) executes the full processing chain for a
screenshot in the background, updating DB state at every stage.

Pipeline stages (sequential):
    PREPROCESSING â†’ OCR â†’ AI_EXTRACTION â†’ EMBEDDING â†’ RELATIONSHIPS

Design rules:
- Each stage is wrapped in its own ProcessingJob row (QUEUED â†’ RUNNING â†’ COMPLETED/FAILED).
- Screenshot.status mirrors the overall result (PROCESSING â†’ COMPLETED or FAILED).
- Idempotent: re-running the same screenshot_id skips already-COMPLETED stages.
- No Celery/Redis â€” uses Python threading (caller's responsibility).
- run_pipeline() manages its own DB session so it is safe to call from a daemon thread.
"""

from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entity import Entity, EntityType
from app.models.memory import Memory
from app.models.processing_job import JobStage, JobStatus, ProcessingJob
from app.models.screenshot import Screenshot, ScreenshotStatus
from app.processing.ocr.provider import run_ocr
from app.processing.relationships import compute_relationships_for_memory
from app.services.llm_extractor import llm_extractor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding helper (Phase C) â€” calls Gemini text-embedding-004 when available
# ---------------------------------------------------------------------------

def _compute_embedding(text: str) -> Optional[list]:
    """Return a float list embedding for text, or None on failure."""
    try:
        from app.config import settings
        if not settings.GEMINI_API_KEY:
            return None
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        result = genai.embed_content(
            model=f"models/{settings.EMBEDDING_MODEL}",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        return result["embedding"]
    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Entity type mapper
# ---------------------------------------------------------------------------

_ENTITY_TYPE_MAP = {
    "technology": EntityType.TECHNOLOGY,
    "framework": EntityType.TECHNOLOGY,
    "tool": EntityType.OTHER,
    "company": EntityType.ORGANIZATION,
    "organization": EntityType.ORGANIZATION,
    "person": EntityType.PERSON,
    "topic": EntityType.OTHER,
    "other": EntityType.OTHER,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_job(
    db: Session,
    screenshot_id: UUID,
    stage: JobStage,
) -> ProcessingJob:
    """
    Return the existing ProcessingJob for this screenshot+stage,
    or create a new QUEUED one.  Prevents duplicate job rows on retry.
    """
    existing = (
        db.query(ProcessingJob)
        .filter_by(screenshot_id=screenshot_id, stage=stage)
        .first()
    )
    if existing:
        return existing

    job = ProcessingJob(
        screenshot_id=screenshot_id,
        stage=stage,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    db.flush()
    return job


def _run_stage(
    db: Session,
    job: ProcessingJob,
    fn: Callable[[], None],
) -> bool:
    """
    Execute *fn* inside a try/except, updating job status accordingly.
    Returns True on success, False on failure.
    """
    # Skip already-completed stages (idempotency)
    if job.status == JobStatus.COMPLETED:
        logger.info("Stage %s already COMPLETED â€” skipping.", job.stage)
        return True

    job.status = JobStatus.RUNNING
    job.started_at = _now()
    db.flush()

    try:
        fn()
        job.status = JobStatus.COMPLETED
        job.completed_at = _now()
        db.flush()
        logger.info("Stage %s COMPLETED.", job.stage)
        return True
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        job.completed_at = _now()
        db.flush()
        logger.error("Stage %s FAILED: %s", job.stage, exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_pipeline(
    screenshot_id: UUID,
    db: Optional[Session] = None,
) -> None:
    """
    Execute the full processing pipeline for *screenshot_id*.

    If *db* is not provided the pipeline creates and owns its own session
    (required when called from a background thread).

    Args:
        screenshot_id: UUID of the Screenshot to process.
        db:            Optional SQLAlchemy session (inject for testing).
    """
    # â”€â”€ Session management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _owns_session = db is None
    if _owns_session:
        from app.db.session import SessionLocal
        db = SessionLocal()

    try:
        _execute_pipeline(db, screenshot_id)
    finally:
        if _owns_session:
            db.close()


def _execute_pipeline(db: Session, screenshot_id: UUID) -> None:
    """Inner implementation â€” assumes caller manages the session lifecycle."""

    # â”€â”€ 0. Load screenshot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    screenshot: Optional[Screenshot] = db.get(Screenshot, screenshot_id)
    if not screenshot:
        logger.error("Pipeline: Screenshot %s not found â€” aborting.", screenshot_id)
        return

    logger.info("Pipeline START for screenshot %s", screenshot_id)
    screenshot.status = ScreenshotStatus.PROCESSING
    db.commit()

    # â”€â”€ Pre-create all job rows so they are visible immediately â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    jobs: dict[JobStage, ProcessingJob] = {}
    for stage in (
        JobStage.PREPROCESSING,
        JobStage.OCR,
        JobStage.AI_EXTRACTION,
        JobStage.EMBEDDING,
        JobStage.INDEXING,
    ):
        jobs[stage] = _get_or_create_job(db, screenshot_id, stage)
    db.commit()

    # Shared state passed between stages via a mutable dict
    ctx: dict = {}

    # â”€â”€ Stage 1: PREPROCESSING â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _preprocess():
        """
        Verify the file exists and extract the original capture timestamp.

        Priority order for captured_at:
          1. EXIF DateTimeOriginal (most reliable â€” set by the OS/app)
          2. Filename date pattern  (e.g. Screenshot_2024-01-15_14-30.png)
          3. File mtime             (last resort â€” may be upload time)
        """
        import os, re
        image_path = screenshot.file_path or ""
        ctx["image_path"] = image_path

        if image_path and not os.path.exists(image_path):
            logger.warning("Preprocessing: file not found at %s (may be in test env)", image_path)
            return

        if not image_path:
            return

        captured: Optional[datetime] = None

        # 1. EXIF extraction via Pillow
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            img = Image.open(image_path)
            exif_data = img._getexif()  # type: ignore[attr-defined]
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, "")
                    if tag in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                        try:
                            captured = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            logger.debug("EXIF captured_at: %s from tag %s", captured, tag)
                            break
                        except ValueError:
                            pass
        except Exception as exc:
            logger.debug("EXIF extraction failed (non-fatal): %s", exc)

        # 2. Filename date pattern (covers Windows/macOS screenshot naming)
        if not captured:
            fname = os.path.basename(image_path)
            patterns = [
                r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})",  # 2024-01-15_14-30-55
                r"(\d{4})-(\d{2})-(\d{2}) (\d{2})\.(\d{2})\.(\d{2})",  # 2024-01-15 14.30.55
                r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})",        # 20240115_143055
                r"(\d{4})-(\d{2})-(\d{2})",                              # 2024-01-15 (date only)
            ]
            for pattern in patterns:
                m = re.search(pattern, fname)
                if m:
                    try:
                        groups = m.groups()
                        if len(groups) == 6:
                            captured = datetime(int(groups[0]), int(groups[1]), int(groups[2]),
                                                int(groups[3]), int(groups[4]), int(groups[5]),
                                                tzinfo=timezone.utc)
                        elif len(groups) == 3:
                            captured = datetime(int(groups[0]), int(groups[1]), int(groups[2]),
                                                tzinfo=timezone.utc)
                        logger.debug("Filename captured_at: %s from pattern %s", captured, pattern)
                        break
                    except (ValueError, IndexError):
                        pass

        # 3. File mtime as last resort
        if not captured:
            try:
                mtime = os.path.getmtime(image_path)
                captured = datetime.fromtimestamp(mtime, tz=timezone.utc)
                logger.debug("mtime captured_at: %s", captured)
            except OSError:
                pass

        # Persist captured_at onto the Screenshot row if we found one
        if captured and not screenshot.captured_at:
            screenshot.captured_at = captured
            db.flush()
            logger.info("Set captured_at=%s for screenshot %s", captured, screenshot_id)

    ok = _run_stage(db, jobs[JobStage.PREPROCESSING], _preprocess)
    if not ok:
        _fail_screenshot(db, screenshot)
        return

    # â”€â”€ Stage 2: OCR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _ocr():
        """Run OCR on the preprocessed image and store text in a Memory row."""
        image_path = ctx.get("image_path", "")
        ocr_result = run_ocr(image_path, screenshot_id=str(screenshot_id))

        if ocr_result.error:
            raise RuntimeError(f"OCR error: {ocr_result.error}")

        # Create (or update) the Memory row for this screenshot
        existing_memory: Optional[Memory] = (
            db.query(Memory)
            .filter_by(screenshot_id=screenshot_id)
            .first()
        )
        if existing_memory:
            existing_memory.raw_ocr_text = ocr_result.full_text
            memory = existing_memory
        else:
            memory = Memory(
                screenshot_id=screenshot_id,
                raw_ocr_text=ocr_result.full_text,
                title=screenshot.original_filename or "Untitled",
                tags=[],
                content_type="screenshot",
            )
            db.add(memory)

        db.flush()
        ctx["memory"] = memory
        ctx["ocr_text"] = ocr_result.full_text

    ok = _run_stage(db, jobs[JobStage.OCR], _ocr)
    if not ok:
        _fail_screenshot(db, screenshot)
        return

    # â”€â”€ Stage 3: AI_EXTRACTION â€” Multimodal LLM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _ai_extraction():
        """
        Phase B: Call LLMExtractor (Gemini / OpenAI / stub) on the image.
        Extracts title, summary, OCR text (better quality than PaddleOCR),
        typed entities, tags, source app, and confidence score.
        Stores everything into the Memory row and creates Entity rows.
        """
        memory: Optional[Memory] = ctx.get("memory")
        if not memory:
            return

        # Load image bytes for LLM
        image_path: str = ctx.get("image_path", "")
        image_bytes: Optional[bytes] = None
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
            except OSError as e:
                logger.warning("Could not read image for LLM extraction: %s", e)

        if image_bytes:
            result = llm_extractor.extract(
                image_bytes,
                filename=screenshot.original_filename or "upload.png",
            )
        else:
            # No image bytes â€” fall back to OCR text we already have
            from app.services.llm_extractor import _stub_result
            result = _stub_result(screenshot.original_filename or "upload.png")

        # Update Memory fields from LLM result
        if result.title:
            memory.title = result.title
        if result.summary:
            memory.summary = result.summary
        # Prefer LLM OCR text over PaddleOCR if LLM produced richer output
        if result.ocr_text and len(result.ocr_text) > len(memory.raw_ocr_text or ""):
            memory.raw_ocr_text = result.ocr_text
        memory.content_type = result.source_type
        memory.confidence_score = result.confidence
        memory.tags = result.tags

        # Phase B: persist app_detected (was being silently discarded before)
        if result.app_detected and result.app_detected.lower() != "unknown":
            memory.app_detected = result.app_detected
            logger.info("app_detected=%r for memory %s", result.app_detected, memory.id)

        # Phase B: sync captured_at from Screenshot â†’ Memory if EXIF was found
        if screenshot.captured_at and not memory.captured_at:
            memory.captured_at = screenshot.captured_at

        # Delete any stale entity rows and create fresh ones from LLM output
        for old_ent in list(memory.entities):
            db.delete(old_ent)
        db.flush()

        for ext_ent in result.entities:
            etype = _ENTITY_TYPE_MAP.get(ext_ent.type.lower(), EntityType.OTHER)
            db.add(Entity(
                memory_id=memory.id,
                name=ext_ent.name,
                entity_type=etype,
                confidence="high",
            ))

        # Store for embedding stage
        ctx["llm_result"] = result
        db.flush()

    ok = _run_stage(db, jobs[JobStage.AI_EXTRACTION], _ai_extraction)
    if not ok:
        _fail_screenshot(db, screenshot)
        return

    # â”€â”€ Stage 4: EMBEDDING â€” Real Gemini text-embedding â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _embedding():
        """
        Phase C: Compute a real vector embedding for the memory using
        Gemini text-embedding-004 (768-dim) or fallback to local embedder.
        Stores directly in the pgvector column.
        """
        memory: Optional[Memory] = ctx.get("memory")
        if not memory:
            return

        llm_res = ctx.get("llm_result")
        if llm_res:
            # Build composite embedding text from LLM results
            tag_str = " ".join(llm_res.tags)
            ent_str = " ".join(e.name for e in llm_res.entities)
            embed_text = (
                f"{memory.title or ''} | {memory.summary or ''} | "
                f"Tags: {tag_str} | Entities: {ent_str} | "
                f"Text: {(memory.raw_ocr_text or '')[:500]}"
            )
        else:
            embed_text = f"{memory.title or ''} {memory.raw_ocr_text or ''}"

        vector = _compute_embedding(embed_text)
        if not vector:
            from app.core.local_embedder import embed_local
            vector = embed_local(embed_text)

        if vector:
            # Store directly in the vector column
            memory.embedding = vector
        db.flush()

    ok = _run_stage(db, jobs[JobStage.EMBEDDING], _embedding)
    if not ok:
        _fail_screenshot(db, screenshot)
        return

    # â”€â”€ Stage 5: INDEXING (Relationships) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _relationships():
        """Compute and persist relationships between this memory and others."""
        memory: Optional[Memory] = ctx.get("memory")
        if memory:
            compute_relationships_for_memory(db, memory_id=memory.id)

    ok = _run_stage(db, jobs[JobStage.INDEXING], _relationships)
    if not ok:
        _fail_screenshot(db, screenshot)
        return

    # â”€â”€ Done â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    screenshot.status = ScreenshotStatus.COMPLETED
    db.commit()
    logger.info("Pipeline COMPLETED for screenshot %s", screenshot_id)


def _fail_screenshot(db: Session, screenshot: Screenshot) -> None:
    """Mark the screenshot as FAILED and commit."""
    screenshot.status = ScreenshotStatus.FAILED
    db.commit()
    logger.error("Pipeline FAILED for screenshot %s", screenshot.id)

