# PROJECT: MemoryLens

## Goal
MemoryLens is a digital-memory interface.
The core concept is:
Capture digital activity → understand it → structure it as a Memory → connect related Memories → allow the user to retrieve and explore them.

## Current Architecture
The project now includes both a fully functional React frontend and a FastAPI backend with a PostgreSQL/pgvector database. 
- It uses AI to perform vision OCR and extract entities from uploaded screenshots.
- It computes semantic and temporal relationships to build a Knowledge Graph of your digital activity.

Please see `DEVELOPER.md` in the root of the repository for instructions on how to set up the backend and frontend.

## Explicitly OUT OF SCOPE
- NO authentication (Do NOT create login/signup/profile/logout functionality)
- NO real OS-level screenshot monitoring daemon (upload is manual or folder-based for now)
