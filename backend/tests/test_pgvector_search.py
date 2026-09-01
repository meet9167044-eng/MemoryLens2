import pytest
from datetime import datetime, timezone, timedelta
from app.models.memory import Memory
from app.models.screenshot import Screenshot, ScreenshotStatus
from app.services.db_search import DBSearchService
from app.schemas.search import SearchRequest
from app.db.session import SessionLocal

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def mock_db_data(db_session):
    db_session.query(Memory).delete()
    db_session.query(Screenshot).delete()
    db_session.commit()

    ss1 = Screenshot(file_path="fake1.png", original_filename="fake1.png", file_size_bytes=100, mime_type="image/png", status=ScreenshotStatus.COMPLETED)
    ss2 = Screenshot(file_path="fake2.png", original_filename="fake2.png", file_size_bytes=100, mime_type="image/png", status=ScreenshotStatus.COMPLETED)
    db_session.add_all([ss1, ss2])
    db_session.commit()

    now = datetime.now(timezone.utc)
    m1 = Memory(
        screenshot_id=ss1.id,
        title="CUDA Error log",
        summary="Error when running training on GPU",
        captured_at=now - timedelta(days=2),
        embedding=[0.1] * 768,
        app_detected="VS Code",
        content_type="terminal"
    )
    m2 = Memory(
        screenshot_id=ss2.id,
        title="React App screenshot",
        summary="Frontend UI testing",
        captured_at=now - timedelta(days=1),
        embedding=[-0.1] * 768,
        app_detected="Chrome",
        content_type="browser"
    )
    db_session.add_all([m1, m2])
    db_session.commit()
    
    return [m1, m2]

def test_pgvector_search_ann_ordering(db_session, mock_db_data):
    # Ensure no rows are loaded entirely in python for ranking if we have pgvector
    svc = DBSearchService(db_session)
    # With q="CUDA Error", it should embed and then use cosine_distance
    # Note: embed_query depends on external API or local sentence transformers, which we may mock or it will run local
    req = SearchRequest(q="CUDA Error", limit=10, offset=0)
    res = svc.search(req)
    assert res.total >= 1
    assert "CUDA" in res.results[0].title

def test_pgvector_search_date_filter(db_session, mock_db_data):
    m1, m2 = mock_db_data
    svc = DBSearchService(db_session)
    
    # Filter for last 24 hours, should only return m2
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(hours=26)).isoformat()
    date_to = (now - timedelta(hours=2)).isoformat()

    req = SearchRequest(q="React", limit=10, offset=0, date_from=date_from, date_to=date_to)
    res = svc.search(req)
    assert res.total == 1
    assert res.results[0].id == str(m2.id)

def test_pgvector_empty_db(db_session):
    svc = DBSearchService(db_session)
    req = SearchRequest(q="Anything", limit=10, offset=0)
    res = svc.search(req)
    assert res.total == 0
    assert len(res.results) == 0
