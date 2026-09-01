import sys
import os

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.memory import Memory
from app.processing.relationships import compute_relationships_for_memory

def main():
    db = SessionLocal()
    memories = db.query(Memory).all()
    count = 0
    for m in memories:
        try:
            rels = compute_relationships_for_memory(db, memory_id=m.id, min_score=0.1)
            count += len(rels)
        except Exception as e:
            print(f"Error on {m.id}: {e}")
    print(f"Computed {count} dynamic relationships!")

if __name__ == '__main__':
    main()
