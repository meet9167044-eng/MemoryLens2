import sys
sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from app.models.memory import Memory
from sqlalchemy import or_, cast, String

db = SessionLocal()
mem = db.query(Memory).first()
if mem and mem.tags:
    print('Testing tag filters...')
    tag_filters = [Memory.tags.cast(String).ilike('%\"' + t + '\"%') for t in mem.tags]
    tag_candidates = (
        db.query(Memory.id)
        .filter(Memory.id != mem.id)
        .filter(or_(*tag_filters))
        .all()
    )
    print(f'Tag candidates: {len(tag_candidates)}')
else:
    print('No memory with tags found')
