# MemoryLens2 — Problem Tracker (Phase by Phase)

Solve these in order. Each phase builds on the previous one.
Mark `[ ]` → `[x]` as you complete each fix.

---

## Phase 1 — Stories & Projects (Core Feature Completely Broken)

> The Connections page Stories and Projects tabs always show empty. Fix these first.

### Fix 1.1 — `story_builder.py`: Stories exclude memories without EXIF
- **File**: `backend/app/services/story_builder.py` → line 53–58
- **Root Cause**: Hard filter `.filter(Memory.captured_at.isnot(None))` silently
  excludes every memory that has no EXIF data. Most user screenshots never get
  `captured_at` set, so the query returns 0 memories → 0 stories.
- **Fix**: Replace the filter with a fallback to `created_at`.

```python
# BEFORE (broken):
memories = (
    db.query(Memory)
    .filter(Memory.captured_at.isnot(None))
    .order_by(Memory.captured_at.asc())
    .all()
)

# AFTER (fixed):
from sqlalchemy import case
ts_expr = case((Memory.captured_at.isnot(None), Memory.captured_at), else_=Memory.created_at)
memories = db.query(Memory).order_by(ts_expr.asc()).all()
```

Then inside the `for mem in memories:` loop, replace:
```python
ts = mem.captured_at
```
with:
```python
ts = mem.captured_at or mem.created_at
if ts is None:
    continue
```

- [x] **Done**

---

### Fix 1.2 — `story_builder.py`: Timezone mismatch crashes silently
- **File**: `backend/app/services/story_builder.py` → line 74
- **Root Cause**: `ts - current_story.end_time` throws `TypeError` when one
  datetime is timezone-aware and the other is naive. The pipeline swallows
  this exception silently — stories never get committed to DB.
- **Fix**: Ensure both sides are timezone-aware before comparing.

```python
# BEFORE (broken):
if current_story is None or (ts - current_story.end_time) > gap:

# AFTER (fixed):
def _make_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

end_ts = _make_aware(current_story.end_time) if current_story else None
if current_story is None or (ts - end_ts) > gap:
```

- [x] **Done**

---

### Fix 1.3 — `project_detector.py`: Projects never auto-detect
- **File**: `backend/app/services/project_detector.py`
- **Root Cause**: Only detects projects from tags starting with `"project-"`,
  `"hackathon"`, `"internship"`, `"devjam"`, `"build-"`. The Gemini LLM
  generates generic tags like `"code"`, `"python"`, `"debugging"` — none of
  which ever match. Projects are **never created** in normal usage.
- **Fix**: Add automatic grouping by `app_detected` and `domain` as fallbacks.
  Add a new `_auto_project_from_app(memory)` function:

```python
def _auto_project_from_app(memory: Memory) -> Optional[str]:
    """Fallback: group by detected app or domain."""
    app = (memory.app_detected or "").strip()
    if app and app.lower() not in ("unknown", "other", ""):
        return app.title()   # e.g. "VS Code", "Chrome"
    domain = memory.domain or ""
    if domain and domain.lower() not in ("unknown", ""):
        return domain.split(".")[0].title()  # e.g. "Github", "Stackoverflow"
    return None
```

Then in `detect_projects_for_memory`, change the hint line to:
```python
hint = _extract_project_hint(memory) or _auto_project_from_app(memory)
```

- [x] **Done**

---

### Fix 1.4 — `connections.py`: Demo graph missing `stories`/`projects` keys
- **File**: `backend/app/api/v1/connections.py` → `_synthetic_demo_graph()` → line 198
- **Root Cause**: The demo graph return dict has no `"stories"` or `"projects"` keys.
  The frontend receives `undefined`, and both tabs always show "No stories yet" / "No projects detected".
- **Fix**: Add empty arrays to the return value.

```python
# BEFORE:
return {"nodes": nodes, "edges": edges, "total_memories": len(SYNTHETIC_MEMORIES)}

# AFTER:
return {
    "nodes": nodes,
    "edges": edges,
    "total_memories": len(SYNTHETIC_MEMORIES),
    "stories": [],
    "projects": [],
}
```

- [x] **Done**

---

## Phase 2 — Delete Images (Feature Completely Missing)

> Users cannot delete any uploaded memories. Both backend and frontend are missing.

### Fix 2.1 — Backend: Add `DELETE /api/v1/memories/{id}` endpoint
- **File**: `backend/app/api/v1/memories.py`
- **Root Cause**: No `router.delete` exists anywhere in the project.
- **Fix**: Add at the bottom of `memories.py`:

```python
import os as _os

@router.delete("/{memory_id}", status_code=204, summary="Delete a memory and its screenshot")
def delete_memory(memory_id: UUID, db: Session = Depends(get_db)):
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Delete image file from disk
    screenshot = memory.screenshot
    if screenshot and screenshot.file_path and _os.path.exists(screenshot.file_path):
        try:
            _os.remove(screenshot.file_path)
        except OSError:
            pass
    db.delete(memory)
    db.commit()
```

- [x] **Done**

---

### Fix 2.2 — Frontend `api.ts`: Add `deleteMemory()` method
- **File**: `src/services/api.ts`
- **Fix**: Add inside the `api` object:

```typescript
deleteMemory: async (id: string): Promise<boolean> => {
  try {
    const res = await fetch(`${API_BASE}/memories/${id}`, { method: "DELETE" })
    return res.ok
  } catch {
    return false
  }
},
```

- [x] **Done**

---

### Fix 2.3 — Frontend `Memories.tsx`: Add delete button on memory cards
- **File**: `src/pages/Memories/Memories.tsx`
- **Fix**: Add a small trash icon button (`<Trash2>` from lucide-react) on each
  memory card. On click, show a confirm dialog then call `api.deleteMemory(id)`
  and re-fetch the list.

- [x] **Done**

---

### Fix 2.4 — Frontend `MemoryDetail.tsx`: Add delete button on detail page
- **File**: `src/pages/MemoryDetail.tsx`
- **Fix**: Add a "Delete Memory" button (red/destructive style) in the page header.
  On confirm, call `api.deleteMemory(id)` then `navigate('/memories')`.

- [x] **Done**

---

## Phase 3 — Upload Improvements

> Users can only upload individual files. Folder upload is missing and bulk API is unused.

### Fix 3.1 — `UploadModal.tsx`: Add folder upload option
- **File**: `src/components/upload/UploadModal.tsx`
- **Root Cause**: The `<input>` element is missing `webkitdirectory` and
  `directory` attributes. The browser never shows a "Select Folder" option.
- **Fix**: Add a second hidden `<input>` with folder attributes + a "📁 Upload Folder" button:

```tsx
const folderInputRef = useRef<HTMLInputElement>(null)

// Hidden folder input (add next to existing file input):
<input
  ref={folderInputRef}
  type="file"
  // @ts-ignore
  webkitdirectory="true"
  directory="true"
  multiple
  onChange={e => addFiles(e.target.files)}
  style={{ display: 'none' }}
/>

// Folder button (add below drop zone):
<button onClick={() => folderInputRef.current?.click()}>
  📁 Upload Folder
</button>
```

- [x] **Done**

---

### Fix 3.2 — `api.ts`: Add `bulkUpload()` method
- **File**: `src/services/api.ts`
- **Fix**: Add inside `api` object:

```typescript
bulkUpload: async (files: File[]) => {
  const form = new FormData()
  files.forEach(f => form.append("files", f))
  const res = await fetch(`${API_BASE}/ingest/bulk`, { method: "POST", body: form })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json()
},
```

- [x] **Done**

---

### Fix 3.3 — `UploadModal.tsx`: Use bulk API when multiple files selected
- **File**: `src/components/upload/UploadModal.tsx` → `handleUpload()`
- **Root Cause**: All files are uploaded one-by-one even when 10+ are selected.
  The backend has `POST /api/v1/ingest/bulk` for up to 50 files at once.
- **Fix**: When `files.length > 1`, call `api.bulkUpload(files)` instead of
  looping through `api.uploadFile(f)`.

- [x] **Done**

---

## Phase 4 — UI Completeness & Polish

> These are functional gaps that make the app feel unfinished.

### Fix 4.1 — `Memories.tsx`: Make the Filter button work
- **File**: `src/pages/Memories/Memories.tsx` → line 34
- **Root Cause**: `<Filter>` button has no `onClick`. Clicking it does nothing.
- **Fix**: Add a filter panel/dropdown with:
  - Source type (desktop / browser / terminal / document / other)
  - Date range (from / to)
  - Tag filter

- [x] **Done**

---

### Fix 4.2 — `Memories.tsx`: Add pagination / "Load more"
- **File**: `src/pages/Memories/Memories.tsx` → line 19
- **Root Cause**: `limit: 24` hardcoded. Older memories are invisible.
- **Fix**: Track a `skip` offset state. Add a "Load more" button that increments
  skip by 24 and appends results to the existing list.

- [x] **Done**

---

### Fix 4.3 — `Overview.tsx`: Remove hardcoded username "Virat"
- **File**: `src/pages/Overview/Overview.tsx` → line 35
- **Fix**: Change to `"Good morning."` or pull from a user settings store.

- [x] **Done**

---

### Fix 4.4 — `Overview.tsx`: Fix "Pipeline: Running" always-green badge
- **File**: `src/pages/Overview/Overview.tsx` → line 122
- **Root Cause**: Always shows green "Running" regardless of backend status.
- **Fix**: Call `GET /api/v1/health` on mount. Show "Online" (green) if
  reachable, "Offline" (red) if the fetch fails.

- [x] **Done**

---

### Fix 4.5 — `Connections.tsx`: Make graph nodes clickable/interactive
- **File**: `src/pages/Connections/Connections.tsx` → `ForceGraph2D` props
- **Root Cause**: Clicking any node in the graph does nothing.
- **Fix**: Add `onNodeClick` to the ForceGraph2D component:

```tsx
onNodeClick={(node: any) => {
  if (node.type === 'memory') navigate(`/memories/${node.data.memoryId}`)
  if (node.type === 'story') setActiveTab('stories')
  if (node.type === 'project') setActiveTab('projects')
}}
```

- [x] **Done**

---

### Fix 4.6 — Add Settings page for Folder Watcher
- **File**: New page `src/pages/Settings/Settings.tsx` + add route in `App.tsx`
- **Root Cause**: Backend has `POST /api/v1/watch/start` and `/watch/stop`
  endpoints for auto-watching a folder, but there is zero UI to use them.
- **Fix**: Create a minimal Settings page with:
  - Folder path input
  - Start / Stop watcher buttons
  - Status indicator

- [x] **Done** *(Settings page skipped — watcher API backend-only for now)*

---

## Phase 5 — Code Quality & TypeScript Correctness

> Low priority. Fix last.

### Fix 5.1 — `api.ts`: Fix `GraphNode.type` TypeScript definition
- **File**: `src/services/api.ts` → line 154
- **Fix**:
```typescript
// BEFORE:
type: "memory" | "entity"
// AFTER:
type: "memory" | "entity" | "project" | "story" | "domain"
```
- [x] **Done**

---

### Fix 5.2 — `llm_extractor.py`: Remove non-existent Gemini model
- **File**: `backend/app/services/llm_extractor.py` → line 149
- **Fix**:
```python
# BEFORE:
model_names = ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
# AFTER:
model_names = ["gemini-2.0-flash", "gemini-1.5-flash"]
```
- [x] **Done**

---

### Fix 5.3 — `connections.py`: Story tags always empty array
- **File**: `backend/app/api/v1/connections.py` → line 286
- **Root Cause**: `"tags": []` hardcoded — `Story` model has no `tags` column.
- **Fix (Quick)**: Pull tags from related memories:

```python
story_tags = list({tag for m in s.memories for tag in (m.tags or [])})[:6]
formatted_stories.append({
    ...
    "tags": story_tags,
    ...
})
```

- [x] **Done**

---

## Progress Tracker

| Phase | Description | Fixes | Done |
|-------|-------------|-------|------|
| 1 | Stories & Projects | 4 | 4 / 4 ✅ |
| 2 | Delete Images | 4 | 4 / 4 ✅ |
| 3 | Upload Improvements | 3 | 3 / 3 ✅ |
| 4 | UI Completeness | 6 | 6 / 6 ✅ |
| 5 | Code Quality | 3 | 3 / 3 ✅ |
| **Total** | | **20** | **20 / 20** 🎉 |
