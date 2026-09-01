import sys
import os

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.memory import Memory
from app.services.story_builder import rebuild_all_stories
from app.services.project_detector import rebuild_all_projects

def main():
    db = SessionLocal()
    print("Rebuilding stories...")
    rebuild_all_stories(db)
    print("Rebuilding projects...")
    rebuild_all_projects(db)
    db.commit()
    print("Patch complete.")

if __name__ == '__main__':
    main()
