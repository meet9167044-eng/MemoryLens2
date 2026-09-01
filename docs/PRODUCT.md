# PRODUCT: MemoryLens

## Overview
The application should feel like a professional developer productivity/productivity-memory tool. It should NOT look like a flashy AI demo.

## Architecture
The application is fully functional, consisting of a React frontend and a FastAPI backend.
Please see `DEVELOPER.md` in the root of the repository for setup instructions.

## User State
There is currently no authentication. The default user is "Virat". 
The Overview greeting should always be: **"Good morning, Virat."**

## Primary Navigation and Screens

### 1. Overview
Provides a quick understanding of the user's digital memory activity.
- **Content:** Greeting, recent memories, recent topics, simple activity summary.
- **Goal:** Keep it minimal. Do not overload the dashboard with charts.

### 2. Memories
The main browsing screen.
- **Content:** Memory cards showing title, source, timestamp, summary, tags.
- **Behavior:** Cards should be clickable and lead to Memory Detail.

### 3. Memory Detail
One of the most important screens.
- **Information Hierarchy:** Evidence ↓ Understanding ↓ Classification ↓ Relationships
- **Content:** title, source, timestamp, screenshot (original evidence), summary, OCR text, entities, tags, related memories.

### 4. Search
- **Behavior:** Full-text keyword search and semantic vector search using pgvector.
- **Searchable fields:** title, OCR text, tags, entities, summary.

### 5. Timeline
Displays Memories chronologically.
- **Behavior:** Items grouped by date/time and clickable. Includes a 12-week activity heatmap.

### 6. Connections
Shows relationships between Memories, Entities, and Topics.
- **Behavior:** Displays structured graph UI linking Semantic Neighbors, Temporal Sequences, Domain Workflows, Projects, and Stories.

### 7. Insights
Shows system analytics based on actual database activity.
- **Content:** OCR confidence, extracted entities, top tags, and processing success metrics.
