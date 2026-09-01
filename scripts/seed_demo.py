"""
scripts/seed_demo.py
====================
Phase H — Demo Data Seeder

Populates the MemoryLens PostgreSQL database with 50 realistic fake memories
across 5 coherent storylines so demos work even without real user data.

STORYLINES
----------
  A. ML / CUDA Debugging (12 memories)   — VS Code, Terminal, Stack Overflow
  B. Internship Application (12 memories) — LinkedIn, Gmail, Google Careers
  C. GitHub Code Review (8 memories)      — GitHub, VS Code
  D. System Setup (10 memories)           — Terminal, Chrome, VS Code
  E. Lecture & Study Session (8 memories) — Chrome, PDF, Notion

USAGE
-----
  cd backend
  python ../scripts/seed_demo.py

  # Optionally wipe first:
  python ../scripts/seed_demo.py --wipe
"""

import sys
import os
import uuid
import hashlib
import argparse
import random
from datetime import datetime, timezone, timedelta

# ── Bootstrap Python path so we can import the backend app ──────────────────
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

os.environ.setdefault("TESTING", "0")  # use real JSONB, not JSON

from app.db.session import SessionLocal, engine  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.screenshot import Screenshot, ScreenshotStatus  # noqa: E402
from app.models.memory import Memory  # noqa: E402
from app.models.entity import Entity, EntityType  # noqa: E402
from app.models.relationship import Relationship, RelationshipType  # noqa: E402

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def ts(year: int, month: int, day: int, hour: int = 10, minute: int = 0) -> datetime:
    """Return a timezone-aware datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def fake_hash(label: str) -> str:
    """Deterministic SHA-256 from a label (so re-runs stay idempotent)."""
    return hashlib.sha256(label.encode()).hexdigest()


def mk_screenshot(label: str, filename: str, captured: datetime, app: str = "Chrome") -> Screenshot:
    return Screenshot(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"screenshot-{label}"),
        file_path=f"demo/screenshots/{label}.png",
        original_filename=filename,
        file_size_bytes=random.randint(80_000, 600_000),
        file_hash=fake_hash(f"demo-{label}"),
        mime_type="image/png",
        status=ScreenshotStatus.COMPLETED,
        captured_at=captured,
    )


def mk_memory(label: str, screenshot: Screenshot, *, title: str, summary: str,
              ocr: str, content_type: str, app: str, domain: str | None,
              tags: list[str], confidence: float = 0.93) -> Memory:
    return Memory(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"memory-{label}"),
        screenshot_id=screenshot.id,
        title=title,
        summary=summary,
        raw_ocr_text=ocr,
        content_type=content_type,
        app_detected=app,
        captured_at=screenshot.captured_at,
        domain=domain,
        tags=tags,
        confidence_score=confidence,
        embedding_placeholder=None,
    )


def mk_entity(memory: Memory, name: str, etype: EntityType, value: str | None = None) -> Entity:
    return Entity(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"entity-{memory.id}-{name}"),
        memory_id=memory.id,
        name=name,
        entity_type=etype,
        value=value,
        confidence="high",
    )


def mk_rel(a: Memory, b: Memory, rel_type: RelationshipType,
           score: float, explanation: str) -> Relationship | None:
    """Create an undirected relationship (source_id < target_id)."""
    sid, tid = sorted([str(a.id), str(b.id)])
    if sid == tid:
        return None
    return Relationship(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"rel-{sid}-{tid}-{rel_type}"),
        source_id=uuid.UUID(sid),
        target_id=uuid.UUID(tid),
        rel_type=rel_type,
        score=round(score, 4),
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# ── STORYLINE A: ML / CUDA Debugging ────────────────────────────────────────
# ---------------------------------------------------------------------------

def build_cuda_storyline():
    base = ts(2026, 1, 12)
    records = []

    # A1 — nvidia-smi check
    sc = mk_screenshot("A1", "Screenshot_2026-01-12_09-45.png", base.replace(hour=9, minute=45), "Terminal")
    m = mk_memory("A1", sc, title="nvidia-smi GPU Status Check",
        summary="Terminal output showing GPU 0 at 98% utilization before training run.",
        ocr="nvidia-smi\nDriver Version: 535.104.05  CUDA Version: 12.2\nGPU 0: NVIDIA RTX 3080  |  10240MiB  |  Volatile GPU-Util: 98%",
        content_type="terminal", app="Terminal", domain=None,
        tags=["gpu", "nvidia", "cuda", "terminal"])
    entities = [
        mk_entity(m, "NVIDIA", EntityType.ORGANIZATION),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY, "12.2"),
        mk_entity(m, "RTX 3080", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # A2 — Training script launch
    sc = mk_screenshot("A2", "Screenshot_2026-01-12_10-02.png", base.replace(hour=10, minute=2), "VS Code")
    m = mk_memory("A2", sc, title="PyTorch CNN Training Script — train.py",
        summary="VS Code showing train.py with DataLoader and model.cuda() calls.",
        ocr="# train.py\nimport torch\nfrom torch.utils.data import DataLoader\nmodel = ResNet50().cuda()\noptimizer = torch.optim.Adam(model.parameters(), lr=1e-4)\nfor epoch in range(100):\n    for batch in train_loader:",
        content_type="code", app="VS Code", domain=None,
        tags=["python", "pytorch", "cuda", "training", "deep-learning"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "ResNet50", EntityType.CODE_SYMBOL),
        mk_entity(m, "train.py", EntityType.FILE_PATH, "/home/meet/ml-project/train.py"),
    ]
    records.append((sc, m, entities))

    # A3 — CUDA OOM error
    sc = mk_screenshot("A3", "Screenshot_2026-01-12_10-18.png", base.replace(hour=10, minute=18), "Terminal")
    m = mk_memory("A3", sc, title="CUDA Out of Memory Error — PyTorch Training",
        summary="RuntimeError: CUDA out of memory during ResNet50 training. GPU tried to allocate 1.45 GiB.",
        ocr="Traceback (most recent call last):\n  File \"train.py\", line 47, in <module>\n    loss = criterion(outputs, labels)\nRuntimeError: CUDA out of memory. Tried to allocate 1.45 GiB (GPU 0; 10.00 GiB total capacity; 8.92 GiB already allocated)",
        content_type="error", app="Terminal", domain=None,
        tags=["error", "cuda", "pytorch", "gpu", "oom"])
    entities = [
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "RuntimeError", EntityType.CODE_SYMBOL),
        mk_entity(m, "train.py", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    # A4 — Stack Overflow CUDA OOM solution
    sc = mk_screenshot("A4", "Screenshot_2026-01-12_10-35.png", base.replace(hour=10, minute=35), "Chrome")
    m = mk_memory("A4", sc, title="Stack Overflow: PyTorch CUDA Out of Memory Fix",
        summary="Stack Overflow answer suggesting gradient accumulation and torch.cuda.empty_cache() to free memory.",
        ocr="stackoverflow.com/questions/pytorch-cuda-out-of-memory\nAnswer: Use gradient accumulation to reduce effective batch size. Call torch.cuda.empty_cache() between epochs.",
        content_type="browser", app="Chrome", domain="stackoverflow.com",
        tags=["stackoverflow", "cuda", "pytorch", "fix", "memory"])
    entities = [
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "stackoverflow.com", EntityType.URL, "https://stackoverflow.com"),
        mk_entity(m, "torch.cuda.empty_cache", EntityType.CODE_SYMBOL),
    ]
    records.append((sc, m, entities))

    # A5 — PyTorch docs memory management
    sc = mk_screenshot("A5", "Screenshot_2026-01-12_11-00.png", base.replace(hour=11, minute=0), "Chrome")
    m = mk_memory("A5", sc, title="PyTorch Docs — CUDA Memory Management",
        summary="Official PyTorch documentation on PYTORCH_CUDA_ALLOC_CONF and max_split_size_mb settings.",
        ocr="pytorch.org/docs/stable/notes/cuda.html\nMemory Management\nSet PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512 to reduce fragmentation.",
        content_type="browser", app="Chrome", domain="pytorch.org",
        tags=["pytorch", "cuda", "documentation", "memory-management"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "pytorch.org", EntityType.URL, "https://pytorch.org"),
        mk_entity(m, "PYTORCH_CUDA_ALLOC_CONF", EntityType.CODE_SYMBOL),
    ]
    records.append((sc, m, entities))

    # A6 — Applying the fix in VS Code
    sc = mk_screenshot("A6", "Screenshot_2026-01-12_11-30.png", base.replace(hour=11, minute=30), "VS Code")
    m = mk_memory("A6", sc, title="Applying Gradient Accumulation Fix in train.py",
        summary="Added gradient accumulation (accum_steps=4) and torch.cuda.empty_cache() after each epoch.",
        ocr="# Fix applied — gradient accumulation\naccum_steps = 4\nfor i, (inputs, labels) in enumerate(train_loader):\n    outputs = model(inputs)\n    loss = criterion(outputs, labels) / accum_steps\n    loss.backward()\n    if (i+1) % accum_steps == 0:\n        optimizer.step()\n        optimizer.zero_grad()\ntorch.cuda.empty_cache()",
        content_type="code", app="VS Code", domain=None,
        tags=["python", "pytorch", "fix", "gradient-accumulation"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "train.py", EntityType.FILE_PATH),
        mk_entity(m, "torch.cuda.empty_cache", EntityType.CODE_SYMBOL),
    ]
    records.append((sc, m, entities))

    # A7 — Training running successfully
    sc = mk_screenshot("A7", "Screenshot_2026-01-12_13-10.png", base.replace(hour=13, minute=10), "Terminal")
    m = mk_memory("A7", sc, title="PyTorch Training Running Successfully",
        summary="Training now progresses without OOM error. Epoch 5/100 at 82% accuracy.",
        ocr="Epoch [5/100]  Loss: 0.2341  Acc: 82.3%  GPU Mem: 6.1/10.0 GiB\nEpoch [6/100]  Loss: 0.2198  Acc: 83.1%  GPU Mem: 6.1/10.0 GiB",
        content_type="terminal", app="Terminal", domain=None,
        tags=["pytorch", "training", "success", "deep-learning"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # A8 — TensorBoard loss curves
    sc = mk_screenshot("A8", "Screenshot_2026-01-13_09-00.png",
                        base.replace(day=13, hour=9, minute=0), "Chrome")
    m = mk_memory("A8", sc, title="TensorBoard — Training Loss Curves",
        summary="TensorBoard showing decreasing training and validation loss over 20 epochs.",
        ocr="localhost:6006 — TensorBoard\ntrain/loss: 0.18 (epoch 20)\nval/loss: 0.21 (epoch 20)\ntrain/accuracy: 91.2%",
        content_type="browser", app="Chrome", domain="localhost",
        tags=["tensorboard", "pytorch", "training", "metrics", "deep-learning"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "TensorBoard", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # A9 — Hugging Face model card research
    sc = mk_screenshot("A9", "Screenshot_2026-01-13_10-30.png",
                        base.replace(day=13, hour=10, minute=30), "Chrome")
    m = mk_memory("A9", sc, title="Hugging Face — ResNet Pretrained Models",
        summary="Browsing microsoft/resnet-50 model card on Hugging Face for transfer learning.",
        ocr="huggingface.co/microsoft/resnet-50\nResNet-50\nPretrained on ImageNet-1k. Top-1 accuracy: 80.6%",
        content_type="browser", app="Chrome", domain="huggingface.co",
        tags=["huggingface", "resnet", "transfer-learning", "pytorch"])
    entities = [
        mk_entity(m, "Hugging Face", EntityType.ORGANIZATION),
        mk_entity(m, "huggingface.co", EntityType.URL, "https://huggingface.co"),
        mk_entity(m, "ResNet50", EntityType.TECHNOLOGY),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # A10 — GitHub Actions CI failure
    sc = mk_screenshot("A10", "Screenshot_2026-01-13_14-00.png",
                        base.replace(day=13, hour=14, minute=0), "Chrome")
    m = mk_memory("A10", sc, title="GitHub Actions — CI Pipeline Failed (CUDA test)",
        summary="GitHub Actions CI failed on the GPU test job due to CUDA unavailability on the runner.",
        ocr="github.com/meet9167044/ml-project/actions\nCI Pipeline ✗ FAILED\nJob: test-gpu\nError: CUDA device not available in runner",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "ci", "cuda", "testing", "devops"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "github.com", EntityType.URL, "https://github.com"),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # A11 — Colab notebook alternative
    sc = mk_screenshot("A11", "Screenshot_2026-01-13_15-15.png",
                        base.replace(day=13, hour=15, minute=15), "Chrome")
    m = mk_memory("A11", sc, title="Google Colab — PyTorch GPU Notebook",
        summary="Moved training to Google Colab for free GPU access. T4 GPU detected.",
        ocr="colab.research.google.com\n!nvidia-smi\nTesla T4\nCUDA: 11.8\nGPU Memory: 15 GiB",
        content_type="browser", app="Chrome", domain="colab.research.google.com",
        tags=["colab", "google", "pytorch", "cuda", "gpu"])
    entities = [
        mk_entity(m, "Google Colab", EntityType.TECHNOLOGY),
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "colab.research.google.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    # A12 — Model checkpoint saved
    sc = mk_screenshot("A12", "Screenshot_2026-01-14_11-00.png",
                        base.replace(day=14, hour=11, minute=0), "Terminal")
    m = mk_memory("A12", sc, title="Model Checkpoint Saved — best_model.pth",
        summary="Training complete. Best model checkpoint saved with 94.7% validation accuracy.",
        ocr="Epoch [47/100]  val_acc=94.7%  ← new best!\nSaving checkpoint to checkpoints/best_model.pth\nEarly stopping triggered at epoch 51.",
        content_type="terminal", app="Terminal", domain=None,
        tags=["pytorch", "training", "checkpoint", "success"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "best_model.pth", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    return records


# ---------------------------------------------------------------------------
# ── STORYLINE B: Internship Application ─────────────────────────────────────
# ---------------------------------------------------------------------------

def build_internship_storyline():
    base = ts(2026, 1, 3)
    records = []

    # B1 — Found internship posting
    sc = mk_screenshot("B1", "Screenshot_2026-01-03_14-20.png",
                        base.replace(hour=14, minute=20), "Chrome")
    m = mk_memory("B1", sc, title="Google SWE Internship 2026 — Job Posting",
        summary="Google Software Engineer Intern Summer 2026 posting on careers.google.com.",
        ocr="careers.google.com\nSoftware Engineer, Intern — Summer 2026\nLocation: Mountain View, CA / Remote\nMinimum qualifications: Currently enrolled in BS/MS/PhD in CS.\nPreferred: Experience with Python, Go, distributed systems.",
        content_type="browser", app="Chrome", domain="careers.google.com",
        tags=["internship", "google", "job-posting", "career"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "careers.google.com", EntityType.URL, "https://careers.google.com"),
        mk_entity(m, "Python", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # B2 — LinkedIn profile update
    sc = mk_screenshot("B2", "Screenshot_2026-01-04_10-00.png",
                        base.replace(day=4, hour=10, minute=0), "Chrome")
    m = mk_memory("B2", sc, title="LinkedIn Profile — Updated for Internship Applications",
        summary="Updating LinkedIn headline and skills section for SWE internship applications.",
        ocr="linkedin.com\nMeet Jain\nComputer Science Student | ML Enthusiast | Seeking SWE Internship 2026\nSkills: Python, PyTorch, FastAPI, PostgreSQL, React",
        content_type="browser", app="Chrome", domain="linkedin.com",
        tags=["linkedin", "profile", "career", "internship"])
    entities = [
        mk_entity(m, "LinkedIn", EntityType.ORGANIZATION),
        mk_entity(m, "linkedin.com", EntityType.URL, "https://linkedin.com"),
        mk_entity(m, "Python", EntityType.TECHNOLOGY),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    # B3 — Resume in VS Code / LaTeX
    sc = mk_screenshot("B3", "Screenshot_2026-01-04_14-30.png",
                        base.replace(day=4, hour=14, minute=30), "VS Code")
    m = mk_memory("B3", sc, title="Resume LaTeX — Updating Work Experience",
        summary="Editing resume.tex in VS Code to add MemoryLens project and recent ML internship.",
        ocr="% resume.tex\n\\section{Projects}\n\\resumeItem{MemoryLens}{AI-powered screenshot search engine using pgvector and FastAPI.}\n\\resumeItem{CNN Classifier}{PyTorch ResNet50 fine-tuned to 94.7\\% accuracy on custom dataset.}",
        content_type="code", app="VS Code", domain=None,
        tags=["resume", "latex", "career", "internship"])
    entities = [
        mk_entity(m, "MemoryLens", EntityType.OTHER),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "resume.tex", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    # B4 — Application submitted
    sc = mk_screenshot("B4", "Screenshot_2026-01-05_09-15.png",
                        base.replace(day=5, hour=9, minute=15), "Chrome")
    m = mk_memory("B4", sc, title="Google Application Submitted Confirmation",
        summary="Confirmation page after submitting the Google SWE Internship 2026 application.",
        ocr="careers.google.com\nApplication Received!\nThank you for applying for: Software Engineer, Intern — Summer 2026\nApplication ID: APP-2026-SWE-471829\nWe'll be in touch within 3 weeks.",
        content_type="browser", app="Chrome", domain="careers.google.com",
        tags=["internship", "google", "application", "career"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "careers.google.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    # B5 — LinkedIn outreach to Googler
    sc = mk_screenshot("B5", "Screenshot_2026-01-06_11-00.png",
                        base.replace(day=6, hour=11, minute=0), "Chrome")
    m = mk_memory("B5", sc, title="LinkedIn — Reached Out to Google Engineer",
        summary="Sent connection request to Google Software Engineer at Mountain View.",
        ocr="linkedin.com/in/sarah-chen-google\nSarah Chen  Software Engineer @ Google\nMessage: Hi Sarah, I recently applied for the SWE Internship at Google and saw your ML infrastructure work...",
        content_type="browser", app="Chrome", domain="linkedin.com",
        tags=["linkedin", "networking", "google", "internship"])
    entities = [
        mk_entity(m, "LinkedIn", EntityType.ORGANIZATION),
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "Sarah Chen", EntityType.PERSON),
    ]
    records.append((sc, m, entities))

    # B6 — Recruiter email
    sc = mk_screenshot("B6", "Screenshot_2026-01-10_08-45.png",
                        base.replace(day=10, hour=8, minute=45), "Chrome")
    m = mk_memory("B6", sc, title="Gmail — Google Recruiter Interview Invitation",
        summary="Email from Google University Recruiting inviting to Technical Phone Screen.",
        ocr="mail.google.com\nFrom: google-recruiting@google.com\nSubject: Next steps — Software Engineer Internship 2026\nHi Meet, We were impressed by your background. We'd like to schedule a technical phone screen.",
        content_type="browser", app="Chrome", domain="mail.google.com",
        tags=["email", "google", "recruiter", "interview", "internship"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "mail.google.com", EntityType.URL, "https://mail.google.com"),
    ]
    records.append((sc, m, entities))

    # B7 — LeetCode interview prep
    sc = mk_screenshot("B7", "Screenshot_2026-01-11_19-00.png",
                        base.replace(day=11, hour=19, minute=0), "Chrome")
    m = mk_memory("B7", sc, title="LeetCode — Graph BFS Problem (Interview Prep)",
        summary="Solving LeetCode #200 'Number of Islands' as Google interview preparation.",
        ocr="leetcode.com/problems/number-of-islands\nNumber of Islands\nDifficulty: Medium  Acceptance: 57.3%\nYour solution runtime: 96ms (beats 89%)",
        content_type="browser", app="Chrome", domain="leetcode.com",
        tags=["leetcode", "interview-prep", "algorithms", "google", "bfs"])
    entities = [
        mk_entity(m, "LeetCode", EntityType.ORGANIZATION),
        mk_entity(m, "leetcode.com", EntityType.URL, "https://leetcode.com"),
        mk_entity(m, "Google", EntityType.ORGANIZATION),
    ]
    records.append((sc, m, entities))

    # B8 — Interview calendar invite
    sc = mk_screenshot("B8", "Screenshot_2026-01-12_09-00.png",
                        base.replace(day=12, hour=9, minute=0), "Chrome")
    m = mk_memory("B8", sc, title="Google Calendar — Technical Phone Screen Scheduled",
        summary="Calendar invite for Google Technical Phone Screen on Jan 17 at 2:00 PM IST.",
        ocr="calendar.google.com\nGoogle Technical Phone Screen\nJanuary 17, 2026  2:00 PM - 3:00 PM IST\nInterviewer: John Smith (Google)\nMeet link: meet.google.com/abc-defg-hij",
        content_type="browser", app="Chrome", domain="calendar.google.com",
        tags=["calendar", "google", "interview", "internship"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "John Smith", EntityType.PERSON),
        mk_entity(m, "calendar.google.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    # B9 — System design notes in VS Code
    sc = mk_screenshot("B9", "Screenshot_2026-01-15_20-00.png",
                        base.replace(day=15, hour=20, minute=0), "VS Code")
    m = mk_memory("B9", sc, title="Interview Prep Notes — System Design Concepts",
        summary="VS Code notes file covering distributed systems, consistent hashing, CAP theorem for Google interview.",
        ocr="# Google Interview Prep\n## System Design\n- Consistent hashing: distributes load evenly across nodes\n- CAP theorem: Consistency, Availability, Partition tolerance — pick 2\n- Load balancer: Round-robin vs. least-connections\n- Database sharding strategies",
        content_type="code", app="VS Code", domain=None,
        tags=["interview-prep", "system-design", "google", "notes"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "CAP theorem", EntityType.OTHER),
    ]
    records.append((sc, m, entities))

    # B10 — Phone screen went well
    sc = mk_screenshot("B10", "Screenshot_2026-01-17_15-30.png",
                        base.replace(day=17, hour=15, minute=30), "Chrome")
    m = mk_memory("B10", sc, title="Google Meet — Post Interview Notes",
        summary="Wrote down key questions asked during the Google phone screen: dynamic programming, graph traversal.",
        ocr="Interview Notes — Jan 17\nQ1: Find shortest path in weighted graph (Dijkstra)\nQ2: Design a URL shortener\nFeeling: Went well, explained trade-offs clearly.\nNext step: Onsite scheduled.",
        content_type="browser", app="Chrome", domain="meet.google.com",
        tags=["interview", "google", "notes", "internship"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "meet.google.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    # B11 — Offer letter email
    sc = mk_screenshot("B11", "Screenshot_2026-01-28_09-30.png",
                        base.replace(day=28, hour=9, minute=30), "Chrome")
    m = mk_memory("B11", sc, title="Gmail — Google Internship Offer Letter",
        summary="Received offer letter email for Google Software Engineer Intern Summer 2026.",
        ocr="mail.google.com\nSubject: Offer — Software Engineer Intern, Summer 2026 @ Google\nDear Meet, We are pleased to extend an offer for a Software Engineer Internship at Google.\nStart Date: May 20, 2026  |  Location: Mountain View, CA",
        content_type="browser", app="Chrome", domain="mail.google.com",
        tags=["offer", "google", "internship", "career", "email"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "mail.google.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    # B12 — LinkedIn post announcing the offer
    sc = mk_screenshot("B12", "Screenshot_2026-01-29_11-00.png",
                        base.replace(day=29, hour=11, minute=0), "Chrome")
    m = mk_memory("B12", sc, title="LinkedIn Post — Excited to Join Google for Summer 2026",
        summary="Posted on LinkedIn announcing acceptance of Google SWE Internship offer.",
        ocr="linkedin.com\nMeet Jain • 1st\nExcited to share that I'll be joining Google as a Software Engineer Intern this Summer 2026! 🎉\n#Google #Internship #SWE #Grateful",
        content_type="browser", app="Chrome", domain="linkedin.com",
        tags=["linkedin", "google", "internship", "announcement", "career"])
    entities = [
        mk_entity(m, "Google", EntityType.ORGANIZATION),
        mk_entity(m, "LinkedIn", EntityType.ORGANIZATION),
        mk_entity(m, "linkedin.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    return records


# ---------------------------------------------------------------------------
# ── STORYLINE C: GitHub Code Review ─────────────────────────────────────────
# ---------------------------------------------------------------------------

def build_github_storyline():
    base = ts(2026, 2, 5)
    records = []

    sc = mk_screenshot("C1", "Screenshot_2026-02-05_10-00.png", base.replace(hour=10), "Chrome")
    m = mk_memory("C1", sc, title="GitHub — Pull Request #42: Add pgvector Search",
        summary="Reviewing open PR to replace O(n) search with pgvector cosine similarity.",
        ocr="github.com/meet9167044/memorylens\nPull Request #42: Add pgvector vector search\nFiles changed: 3  Additions: +287  Deletions: -94\nReviewer comment: LGTM — great improvement over the previous linear scan.",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "pull-request", "pgvector", "code-review"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "pgvector", EntityType.TECHNOLOGY),
        mk_entity(m, "github.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C2", "Screenshot_2026-02-05_11-30.png", base.replace(hour=11, minute=30), "VS Code")
    m = mk_memory("C2", sc, title="VS Code — Resolving Code Review Comments",
        summary="Addressing reviewer feedback on db_search.py — fixing hybrid score weights.",
        ocr="# db_search.py\n# Fix: reviewer requested 0.6/0.4 split instead of 0.5/0.5\nvector_score = 1.0 - float(row.distance)  # cosine\ntextrank_score = row.ts_rank or 0.0\nhybrid = 0.6 * vector_score + 0.4 * textrank_score",
        content_type="code", app="VS Code", domain=None,
        tags=["code-review", "python", "pgvector", "search"])
    entities = [
        mk_entity(m, "pgvector", EntityType.TECHNOLOGY),
        mk_entity(m, "db_search.py", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C3", "Screenshot_2026-02-05_14-00.png", base.replace(hour=14), "Chrome")
    m = mk_memory("C3", sc, title="GitHub Actions — CI All Green After Fix",
        summary="All 23 tests pass after addressing code review comments.",
        ocr="github.com/meet9167044/memorylens/actions\nCI Pipeline ✓ PASSED\n23 tests passed  0 failed  2 skipped\nBuild time: 1m 42s",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "ci", "tests", "passing"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "github.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C4", "Screenshot_2026-02-05_15-00.png", base.replace(hour=15), "Chrome")
    m = mk_memory("C4", sc, title="GitHub — PR Merged: pgvector Search Feature",
        summary="PR #42 merged to main. pgvector-powered hybrid search is now live.",
        ocr="github.com/meet9167044/memorylens/pull/42\nPull Request #42 Merged ✓\nadd-pgvector-search → main\nMerged by meet9167044",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "merged", "pgvector", "milestone"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "pgvector", EntityType.TECHNOLOGY),
        mk_entity(m, "github.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C5", "Screenshot_2026-02-06_09-00.png",
                        base.replace(day=6, hour=9), "Chrome")
    m = mk_memory("C5", sc, title="GitHub Issues — Knowledge Graph Feature Request",
        summary="Opened issue #43 to track the Phase D knowledge graph engine implementation.",
        ocr="github.com/meet9167044/memorylens/issues/43\nIssue #43: Implement Knowledge Graph Engine (Phase D)\nLabels: enhancement, priority:high\nAssigned to: meet9167044",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "issues", "knowledge-graph", "planning"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "github.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C6", "Screenshot_2026-02-06_11-00.png",
                        base.replace(day=6, hour=11), "VS Code")
    m = mk_memory("C6", sc, title="VS Code — Implementing Relationship Engine",
        summary="Writing relationships.py with semantic, temporal, and domain scoring functions.",
        ocr="# relationships.py\ndef _score_semantic(a: Memory, b: Memory) -> tuple[float, str]:\n    sim = 1.0 - cosine_distance(a.embedding, b.embedding)\n    if sim < 0.65:\n        return 0.0, ''\n    return round(sim, 4), f'Semantic similarity: {sim:.0%}'",
        content_type="code", app="VS Code", domain=None,
        tags=["python", "knowledge-graph", "relationships", "code"])
    entities = [
        mk_entity(m, "Python", EntityType.TECHNOLOGY),
        mk_entity(m, "relationships.py", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C7", "Screenshot_2026-02-07_10-00.png",
                        base.replace(day=7, hour=10), "Chrome")
    m = mk_memory("C7", sc, title="GitHub — Commit History: Phase D Progress",
        summary="8 commits over 2 days implementing the knowledge graph engine.",
        ocr="github.com/meet9167044/memorylens/commits/main\nfeat: add temporal relationship scoring\nfeat: add domain relationship scoring\nfeat: add project auto-detector\nfeat: add story builder\n",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "commits", "knowledge-graph"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "github.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("C8", "Screenshot_2026-02-07_16-00.png",
                        base.replace(day=7, hour=16), "Chrome")
    m = mk_memory("C8", sc, title="GitHub — Star Count Milestone: 50 Stars",
        summary="MemoryLens repository hit 50 GitHub stars after sharing on Hacker News.",
        ocr="github.com/meet9167044/memorylens\n★ 50 stars  🍴 12 forks  👁 8 watching\nRecent: Shared on Hacker News — 'Show HN: MemoryLens — search your screenshots'",
        content_type="browser", app="Chrome", domain="github.com",
        tags=["github", "milestone", "open-source"])
    entities = [
        mk_entity(m, "GitHub", EntityType.ORGANIZATION),
        mk_entity(m, "Hacker News", EntityType.ORGANIZATION),
        mk_entity(m, "github.com", EntityType.URL),
    ]
    records.append((sc, m, entities))

    return records


# ---------------------------------------------------------------------------
# ── STORYLINE D: System Setup ────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def build_setup_storyline():
    base = ts(2026, 1, 20)
    records = []

    sc = mk_screenshot("D1", "Screenshot_2026-01-20_09-00.png", base.replace(hour=9), "Terminal")
    m = mk_memory("D1", sc, title="Installing PostgreSQL 16 on Ubuntu 22.04",
        summary="Running apt-get install postgresql-16 and initializing the memorylens_db database.",
        ocr="sudo apt-get install postgresql-16\nSetting up postgresql-16...\nCreating cluster 16/main ...\nStarting PostgreSQL 16: postgresql.",
        content_type="terminal", app="Terminal", domain=None,
        tags=["postgresql", "setup", "linux", "database"])
    entities = [
        mk_entity(m, "PostgreSQL", EntityType.TECHNOLOGY),
        mk_entity(m, "Ubuntu", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D2", "Screenshot_2026-01-20_09-30.png", base.replace(hour=9, minute=30), "Terminal")
    m = mk_memory("D2", sc, title="pgvector Extension Installation",
        summary="Installed pgvector PostgreSQL extension and enabled it in memorylens_db.",
        ocr="sudo apt install postgresql-16-pgvector\npgvector installed successfully.\npsql memorylens_db -c 'CREATE EXTENSION vector;'\nCREATE EXTENSION",
        content_type="terminal", app="Terminal", domain=None,
        tags=["pgvector", "postgresql", "setup", "vector-db"])
    entities = [
        mk_entity(m, "pgvector", EntityType.TECHNOLOGY),
        mk_entity(m, "PostgreSQL", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D3", "Screenshot_2026-01-20_10-00.png", base.replace(hour=10), "Terminal")
    m = mk_memory("D3", sc, title="pip install — Backend Dependencies",
        summary="Installing all Python backend requirements including sentence-transformers and fastapi.",
        ocr="pip install -r requirements.txt\nCollecting fastapi>=0.109.0\nCollecting sentence-transformers>=2.7.0\nCollecting pgvector>=0.2.4\nSuccessfully installed 47 packages.",
        content_type="terminal", app="Terminal", domain=None,
        tags=["python", "pip", "setup", "fastapi", "sentence-transformers"])
    entities = [
        mk_entity(m, "FastAPI", EntityType.TECHNOLOGY),
        mk_entity(m, "Python", EntityType.TECHNOLOGY),
        mk_entity(m, "sentence-transformers", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D4", "Screenshot_2026-01-20_10-30.png", base.replace(hour=10, minute=30), "Terminal")
    m = mk_memory("D4", sc, title="Alembic Migration — upgrade head",
        summary="Running alembic upgrade head to apply all migrations including pgvector extension.",
        ocr="alembic upgrade head\nRunning upgrade -> 2c5f3091dea7, add file hash column\nRunning upgrade -> 2c766c3a59a7, add app detected captured at\nRunning upgrade -> a1b2c3d4e5f6, enable pgvector add embedding\nDone.",
        content_type="terminal", app="Terminal", domain=None,
        tags=["alembic", "database", "migration", "postgresql", "setup"])
    entities = [
        mk_entity(m, "Alembic", EntityType.TECHNOLOGY),
        mk_entity(m, "PostgreSQL", EntityType.TECHNOLOGY),
        mk_entity(m, "pgvector", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D5", "Screenshot_2026-01-20_11-00.png", base.replace(hour=11), "Chrome")
    m = mk_memory("D5", sc, title="FastAPI Swagger Docs — Backend Running",
        summary="FastAPI interactive docs at localhost:8000/docs showing all API endpoints.",
        ocr="localhost:8000/docs\nMemoryLens API — v1.0\nPOST /api/v1/ingest\nGET /api/v1/memories\nGET /api/v1/search\nPOST /api/v1/chat",
        content_type="browser", app="Chrome", domain="localhost",
        tags=["fastapi", "api", "docs", "setup"])
    entities = [
        mk_entity(m, "FastAPI", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D6", "Screenshot_2026-01-20_11-30.png", base.replace(hour=11, minute=30), "Terminal")
    m = mk_memory("D6", sc, title="npm install — Frontend Dependencies",
        summary="Installing React, Vite, and TypeScript frontend dependencies.",
        ocr="npm install\nadded 418 packages in 18s\n1 high severity vulnerability (update vite to >=5.2.10)",
        content_type="terminal", app="Terminal", domain=None,
        tags=["npm", "react", "vite", "typescript", "setup"])
    entities = [
        mk_entity(m, "React", EntityType.TECHNOLOGY),
        mk_entity(m, "Vite", EntityType.TECHNOLOGY),
        mk_entity(m, "TypeScript", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D7", "Screenshot_2026-01-20_12-00.png", base.replace(hour=12), "Chrome")
    m = mk_memory("D7", sc, title="MemoryLens Frontend Running at localhost:5173",
        summary="React frontend running in Vite dev server. Overview page visible with upload UI.",
        ocr="localhost:5173\nMemoryLens\n🔍 Search your memories...\nUpload Screenshot\n0 memories indexed",
        content_type="browser", app="Chrome", domain="localhost",
        tags=["react", "frontend", "vite", "memorylens", "setup"])
    entities = [
        mk_entity(m, "React", EntityType.TECHNOLOGY),
        mk_entity(m, "Vite", EntityType.TECHNOLOGY),
        mk_entity(m, "MemoryLens", EntityType.OTHER),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D8", "Screenshot_2026-01-20_14-00.png", base.replace(hour=14), "Chrome")
    m = mk_memory("D8", sc, title="SentenceTransformers Model Download Progress",
        summary="all-mpnet-base-v2 model downloading (420MB). Used for local embeddings without API key.",
        ocr="Downloading all-mpnet-base-v2\n420MB / 420MB [========] 100%  2.1 MB/s\nSaving model to /home/meet/.cache/sentence_transformers/all-mpnet-base-v2",
        content_type="browser", app="Chrome", domain="localhost",
        tags=["sentence-transformers", "model", "embeddings", "setup"])
    entities = [
        mk_entity(m, "sentence-transformers", EntityType.TECHNOLOGY),
        mk_entity(m, "all-mpnet-base-v2", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D9", "Screenshot_2026-01-20_15-00.png", base.replace(hour=15), "Terminal")
    m = mk_memory("D9", sc, title="First Screenshot Ingested — Pipeline Completed",
        summary="Test screenshot processed through full 5-stage pipeline in 4.2 seconds.",
        ocr="[Pipeline] screenshot_id=abc123\n[1/5] Preprocessing... done (0.1s)\n[2/5] OCR... done (1.4s)  800 chars extracted\n[3/5] AI Extraction... done (2.1s)  app=VS Code, 3 entities\n[4/5] Embedding... done (0.4s)  768-dim vector stored\n[5/5] Relationships... done (0.2s)  0 relationships\nPipeline complete in 4.2s",
        content_type="terminal", app="Terminal", domain=None,
        tags=["pipeline", "memorylens", "ingest", "setup", "success"])
    entities = [
        mk_entity(m, "MemoryLens", EntityType.OTHER),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("D10", "Screenshot_2026-01-20_15-30.png", base.replace(hour=15, minute=30), "Chrome")
    m = mk_memory("D10", sc, title="MemoryLens Search Working — Found CUDA Error",
        summary="Search query 'CUDA error' returns correct screenshot with 0.91 confidence. Search works!",
        ocr="localhost:5173/search?q=cuda+error\nResults for 'cuda error'\n1. CUDA Out of Memory Error (score: 0.91)\n   VS Code | Jan 12, 2026\n2. nvidia-smi GPU Check (score: 0.78)\n   Terminal | Jan 12, 2026",
        content_type="browser", app="Chrome", domain="localhost",
        tags=["memorylens", "search", "cuda", "success"])
    entities = [
        mk_entity(m, "CUDA", EntityType.TECHNOLOGY),
        mk_entity(m, "MemoryLens", EntityType.OTHER),
    ]
    records.append((sc, m, entities))

    return records


# ---------------------------------------------------------------------------
# ── STORYLINE E: Lecture & Study Session ────────────────────────────────────
# ---------------------------------------------------------------------------

def build_study_storyline():
    base = ts(2026, 2, 10)
    records = []

    sc = mk_screenshot("E1", "Screenshot_2026-02-10_09-00.png", base.replace(hour=9), "Chrome")
    m = mk_memory("E1", sc, title="Coursera — Deep Learning Specialization Week 4",
        summary="Watching Andrew Ng's lecture on Recurrent Neural Networks and LSTM architecture.",
        ocr="coursera.org/learn/nlp-sequence-models/lecture/0h7gT\nSequence Models — Week 4\nLong Short-Term Memory (LSTM)\n'The key to LSTM is the cell state — the horizontal line running through the top.'",
        content_type="browser", app="Chrome", domain="coursera.org",
        tags=["coursera", "deep-learning", "lstm", "lecture", "andrew-ng"])
    entities = [
        mk_entity(m, "Coursera", EntityType.ORGANIZATION),
        mk_entity(m, "coursera.org", EntityType.URL, "https://coursera.org"),
        mk_entity(m, "Andrew Ng", EntityType.PERSON),
        mk_entity(m, "LSTM", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E2", "Screenshot_2026-02-10_10-30.png", base.replace(hour=10, minute=30), "VS Code")
    m = mk_memory("E2", sc, title="VS Code — LSTM Implementation from Scratch",
        summary="Implementing LSTM cell in PyTorch following the lecture notes.",
        ocr="# lstm_scratch.py\nimport torch.nn as nn\nclass LSTMCell(nn.Module):\n    def forward(self, x, h_prev, c_prev):\n        combined = torch.cat([x, h_prev], dim=1)\n        i = torch.sigmoid(self.Wi(combined))\n        f = torch.sigmoid(self.Wf(combined))\n        c = f * c_prev + i * torch.tanh(self.Wc(combined))",
        content_type="code", app="VS Code", domain=None,
        tags=["python", "pytorch", "lstm", "deep-learning", "implementation"])
    entities = [
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
        mk_entity(m, "LSTM", EntityType.TECHNOLOGY),
        mk_entity(m, "lstm_scratch.py", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E3", "Screenshot_2026-02-10_14-00.png", base.replace(hour=14), "Chrome")
    m = mk_memory("E3", sc, title="ArXiv — Attention Is All You Need (Transformer Paper)",
        summary="Reading the original Transformer paper for understanding self-attention mechanisms.",
        ocr="arxiv.org/abs/1706.03762\nAttention Is All You Need\nVaswani et al., 2017\n'We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.'",
        content_type="browser", app="Chrome", domain="arxiv.org",
        tags=["arxiv", "transformer", "attention", "research", "nlp"])
    entities = [
        mk_entity(m, "arxiv.org", EntityType.URL, "https://arxiv.org"),
        mk_entity(m, "Transformer", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E4", "Screenshot_2026-02-11_09-00.png",
                        base.replace(day=11, hour=9), "Chrome")
    m = mk_memory("E4", sc, title="Notion — Study Notes: Transformer Architecture",
        summary="Notion page with study notes on multi-head attention, positional encoding, and encoder-decoder.",
        ocr="notion.so/meet/transformer-notes\nTransformer Architecture Notes\n## Multi-Head Attention\n- h=8 parallel attention heads\n- d_model=512, d_k=d_v=64\n## Positional Encoding\n- PE(pos,2i) = sin(pos/10000^(2i/d_model))",
        content_type="browser", app="Chrome", domain="notion.so",
        tags=["notion", "notes", "transformer", "study", "nlp"])
    entities = [
        mk_entity(m, "Notion", EntityType.TECHNOLOGY),
        mk_entity(m, "Transformer", EntityType.TECHNOLOGY),
        mk_entity(m, "notion.so", EntityType.URL, "https://notion.so"),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E5", "Screenshot_2026-02-11_11-00.png",
                        base.replace(day=11, hour=11), "Chrome")
    m = mk_memory("E5", sc, title="Hugging Face — BERT Fine-Tuning Tutorial",
        summary="Tutorial on fine-tuning BERT for text classification using the Transformers library.",
        ocr="huggingface.co/docs/transformers/training\nFine-tune a pretrained model\nfrom transformers import AutoModelForSequenceClassification, Trainer\nmodel = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=5)",
        content_type="browser", app="Chrome", domain="huggingface.co",
        tags=["huggingface", "bert", "transformers", "fine-tuning", "nlp"])
    entities = [
        mk_entity(m, "Hugging Face", EntityType.ORGANIZATION),
        mk_entity(m, "BERT", EntityType.TECHNOLOGY),
        mk_entity(m, "Transformer", EntityType.TECHNOLOGY),
        mk_entity(m, "huggingface.co", EntityType.URL),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E6", "Screenshot_2026-02-11_14-00.png",
                        base.replace(day=11, hour=14), "VS Code")
    m = mk_memory("E6", sc, title="VS Code — BERT Fine-Tuning Script",
        summary="Fine-tuning BERT for sentiment analysis on the SST-2 dataset.",
        ocr="# bert_finetune.py\nfrom transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments\nmodel = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)\ntrainer = Trainer(model=model, args=training_args, train_dataset=tokenized['train'])\ntrainer.train()",
        content_type="code", app="VS Code", domain=None,
        tags=["python", "bert", "huggingface", "fine-tuning", "nlp"])
    entities = [
        mk_entity(m, "BERT", EntityType.TECHNOLOGY),
        mk_entity(m, "Hugging Face", EntityType.ORGANIZATION),
        mk_entity(m, "Python", EntityType.TECHNOLOGY),
        mk_entity(m, "bert_finetune.py", EntityType.FILE_PATH),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E7", "Screenshot_2026-02-12_10-00.png",
                        base.replace(day=12, hour=10), "Chrome")
    m = mk_memory("E7", sc, title="Papers With Code — BERT State of the Art Results",
        summary="Checking BERT benchmark results on GLUE and SQuAD leaderboards.",
        ocr="paperswithcode.com/method/bert\nBERT\nState-of-the-Art on GLUE: 80.5\nState-of-the-Art on SQuAD 1.1: 93.2 F1",
        content_type="browser", app="Chrome", domain="paperswithcode.com",
        tags=["bert", "benchmark", "nlp", "papers-with-code"])
    entities = [
        mk_entity(m, "BERT", EntityType.TECHNOLOGY),
        mk_entity(m, "paperswithcode.com", EntityType.URL, "https://paperswithcode.com"),
    ]
    records.append((sc, m, entities))

    sc = mk_screenshot("E8", "Screenshot_2026-02-12_15-00.png",
                        base.replace(day=12, hour=15), "Terminal")
    m = mk_memory("E8", sc, title="BERT Fine-Tuning Results — 91.4% Accuracy",
        summary="BERT fine-tuning complete. Achieved 91.4% accuracy on SST-2 test set.",
        ocr="***** Running Evaluation *****\n  Num examples = 872\n  Batch size = 32\neval_accuracy = 0.9140\neval_loss = 0.2341\nTraining completed!",
        content_type="terminal", app="Terminal", domain=None,
        tags=["bert", "training", "success", "nlp", "accuracy"])
    entities = [
        mk_entity(m, "BERT", EntityType.TECHNOLOGY),
        mk_entity(m, "PyTorch", EntityType.TECHNOLOGY),
    ]
    records.append((sc, m, entities))

    return records


# ---------------------------------------------------------------------------
# ── RELATIONSHIP BUILDER ────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def build_relationships(all_memories: list[Memory]) -> list[Relationship]:
    """Build realistic cross-memory relationships based on storyline knowledge."""

    # Index by label for easy lookup
    idx = {m.title[:20]: m for m in all_memories}

    def find(label_fragment: str) -> Memory | None:
        for title, mem in idx.items():
            if label_fragment.lower() in mem.title.lower():
                return mem
        return None

    rels: list[Relationship] = []

    def add(a: Memory | None, b: Memory | None, rtype: RelationshipType,
            score: float, explanation: str):
        if a is None or b is None:
            return
        r = mk_rel(a, b, rtype, score, explanation)
        if r:
            rels.append(r)

    # ── Storyline A: CUDA cluster ──────────────────────────────────────────
    cuda_mems = [m for m in all_memories if "CUDA" in m.tags or "cuda" in (m.tags or [])]
    for i, ma in enumerate(cuda_mems):
        for mb in cuda_mems[i + 1:]:
            # Temporal
            if ma.captured_at and mb.captured_at:
                delta = abs((ma.captured_at - mb.captured_at).total_seconds())
                if delta < 7200:
                    score = round(1.0 - (delta / 7200), 4)
                    add(ma, mb, RelationshipType.TEMPORAL, score,
                        f"Captured {int(delta/60)} min apart")
            # Shared entity (CUDA)
            add(ma, mb, RelationshipType.SHARED_ENTITY, 0.85,
                "Both mention CUDA")

    # ── Storyline B: Internship cluster ───────────────────────────────────
    intern_mems = [m for m in all_memories if "internship" in (m.tags or []) or
                   "google" in (m.tags or [])]
    for i, ma in enumerate(intern_mems):
        for mb in intern_mems[i + 1:]:
            add(ma, mb, RelationshipType.SHARED_ENTITY, 0.9,
                "Both mention Google internship")
            if ma.captured_at and mb.captured_at:
                delta = abs((ma.captured_at - mb.captured_at).total_seconds())
                if delta < 7 * 86400:
                    add(ma, mb, RelationshipType.TEMPORAL,
                        round(max(0.3, 1.0 - delta / (7 * 86400)), 4),
                        "Same internship application week")

    # ── Storyline C: GitHub cluster ────────────────────────────────────────
    gh_mems = [m for m in all_memories if m.domain == "github.com"]
    for i, ma in enumerate(gh_mems):
        for mb in gh_mems[i + 1:]:
            add(ma, mb, RelationshipType.DOMAIN, 0.7, "Same domain: github.com")
            if ma.captured_at and mb.captured_at:
                delta = abs((ma.captured_at - mb.captured_at).total_seconds())
                if delta < 7200:
                    add(ma, mb, RelationshipType.TEMPORAL,
                        round(1.0 - (delta / 7200), 4),
                        f"Captured {int(delta/60)} min apart")

    # ── Cross-storyline semantic links ────────────────────────────────────
    pytorch_mems = [m for m in all_memories if "pytorch" in (m.tags or []) or
                    "PyTorch" in (m.tags or [])]
    for i, ma in enumerate(pytorch_mems):
        for mb in pytorch_mems[i + 1:]:
            add(ma, mb, RelationshipType.SHARED_ENTITY, 0.82,
                "Both mention PyTorch")

    # ── Shared tag: deep-learning ─────────────────────────────────────────
    dl_mems = [m for m in all_memories if "deep-learning" in (m.tags or [])]
    for i, ma in enumerate(dl_mems):
        for mb in dl_mems[i + 1:]:
            add(ma, mb, RelationshipType.SHARED_TAG, 0.75,
                "Shared tag: deep-learning")

    # ── Hugging Face domain cluster ────────────────────────────────────────
    hf_mems = [m for m in all_memories if m.domain == "huggingface.co"]
    for i, ma in enumerate(hf_mems):
        for mb in hf_mems[i + 1:]:
            add(ma, mb, RelationshipType.DOMAIN, 0.72, "Same domain: huggingface.co")

    # ── Stack Overflow ─────────────────────────────────────────────────────
    so_mem = find("Stack Overflow")
    cuda_err = find("CUDA Out of Memory Error")
    if so_mem and cuda_err:
        add(so_mem, cuda_err, RelationshipType.SEMANTIC, 0.91,
            "Stack Overflow answer directly addresses CUDA OOM error")

    # ── Interview prep → phone screen ─────────────────────────────────────
    prep = find("Interview Prep Notes")
    screen = find("Post Interview Notes")
    if prep and screen:
        add(prep, screen, RelationshipType.TEMPORAL, 0.88,
            "Prep notes written 2 days before the phone screen")

    # Deduplicate by (source_id, target_id, rel_type)
    seen = set()
    unique: list[Relationship] = []
    for r in rels:
        key = (str(r.source_id), str(r.target_id), r.rel_type)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


# ---------------------------------------------------------------------------
# ── MAIN ────────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed MemoryLens demo data")
    parser.add_argument("--wipe", action="store_true",
                        help="Delete ALL existing data before seeding (destructive!)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.wipe:
            print("⚠️  Wiping existing data…")
            db.query(Relationship).delete()
            db.query(Entity).delete()
            db.query(Memory).delete()
            db.query(Screenshot).delete()
            db.commit()
            print("   Done.\n")

        # Collect all storyline data
        storylines = [
            ("A — ML / CUDA Debugging",      build_cuda_storyline()),
            ("B — Internship Application",    build_internship_storyline()),
            ("C — GitHub Code Review",        build_github_storyline()),
            ("D — System Setup",              build_setup_storyline()),
            ("E — Lecture & Study",           build_study_storyline()),
        ]

        all_memories: list[Memory] = []
        total_sc = total_mem = total_ent = 0

        for name, records in storylines:
            print(f"📦 Seeding {name} ({len(records)} memories)…")
            for sc, m, entities in records:
                # Upsert screenshot
                existing_sc = db.get(Screenshot, sc.id)
                if not existing_sc:
                    db.add(sc)
                # Upsert memory
                existing_m = db.get(Memory, m.id)
                if not existing_m:
                    db.add(m)
                    for e in entities:
                        db.add(e)
                    total_sc += 1
                    total_mem += 1
                    total_ent += len(entities)
                all_memories.append(m)

        db.flush()  # ensure IDs are assigned before building relationships

        # Build and upsert relationships
        print("\n🔗 Building relationships…")
        rels = build_relationships(all_memories)
        rel_added = 0
        for r in rels:
            existing = db.get(Relationship, r.id)
            if not existing:
                db.add(r)
                rel_added += 1

        db.commit()

        print("\n✅ Seed complete!")
        print(f"   Screenshots : {total_sc}")
        print(f"   Memories    : {total_mem}")
        print(f"   Entities    : {total_ent}")
        print(f"   Relationships: {rel_added}")
        print("\n💡 Now run the MemoryLens app and explore the demo data:")
        print("   Backend:  cd backend && uvicorn app.main:app --reload")
        print("   Frontend: npm run dev")

    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
