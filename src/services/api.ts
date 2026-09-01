// Absolute URL — backend CORS allows http://localhost:5173 so no proxy is needed.
// If you move to production, swap this for an env variable.
const API_BASE = "http://localhost:8000/api/v1"

// ─── Backend Response Types (exact match to MemoryResponse schema) ─────────

export interface MemorySource {
  app: string
  type: "desktop" | "browser" | "terminal" | "document" | "other"
}

export interface MemoryScreenshot {
  id: string
  imageUrl: string
}

export interface MemoryContent {
  ocrText: string
  title: string
  summary: string
}

export interface MemoryEntity {
  id: string
  name: string
  type: string
}

export interface RelatedMemory {
  memoryId: string
  relationship: string
  similarityScore?: number
}

export interface MemoryMetadata {
  language: string
  contentType: string
  confidence: number
}

export interface Memory {
  id: string
  timestamp: string
  source: MemorySource
  screenshot: MemoryScreenshot
  content: MemoryContent
  entities: MemoryEntity[]
  tags: string[]
  relatedMemories: RelatedMemory[]
  metadata: MemoryMetadata
}

// ─── Insights ───────────────────────────────────────────────────────────────

export interface InsightStats {
  total_memories: number
  total_entities: number
  total_screenshots: number
  recent_activity_count: number
  avg_confidence: number | null
  processing_success_rate: number | null
  completed_screenshots: number
  failed_screenshots: number
  top_tags: { name: string; count: number }[]
  top_entities: { name: string; count: number }[]
  app_breakdown: { name: string; count: number }[]
  activity_by_day?: { date: string; count: number }[]
}

// ─── Search ─────────────────────────────────────────────────────────────────
//
// IMPORTANT: The backend /search endpoint returns SearchResult objects, NOT
// full Memory objects. SearchResult is a *flat* shape for ranked results.
// Do NOT expect content.title or screenshot.imageUrl here.

export interface SearchResultSource {
  app: string
  type: "desktop" | "browser" | "terminal" | "document" | "other"
}

export interface SearchResultEntity {
  id: string
  name: string
  type: string
}

export interface SearchResult {
  id: string
  timestamp: string
  source: SearchResultSource
  title: string
  summary: string
  ocr_snippet: string
  tags: string[]
  entities: SearchResultEntity[]
  image_url: string
  relevance_score: number
  match_type: "semantic" | "keyword" | "hybrid"
}

export interface SearchResponse {
  query: string
  total: number
  limit: number
  offset: number
  results: SearchResult[]
  nlp_applied?: boolean
  facets?: {
    apps?: Record<string, number>
    dates?: Record<string, number>
    types?: Record<string, number>
  }
}

// ─── Ingest ─────────────────────────────────────────────────────────────────

export interface IngestResponse {
  screenshot_id: string
  status: string
  file_path: string
  original_filename: string
  file_size_bytes: number
  file_hash: string
  message: string
}

export interface IngestStatusResponse {
  screenshot_id: string
  status: string
  stage?: string
  original_filename: string
  created_at: string
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export interface ChatCitation {
  memory_id: string
  title: string
  timestamp: string
  snippet: string
}

export interface ChatResponse {
  answer: string
  citations: ChatCitation[]
  memories_searched: number
  model_used: string
}

// ─── Connections ─────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string
  type: "memory" | "entity"
  /** The display name — use `label`, NOT `name` (backend field is `label`) */
  label: string
  data: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
  data: Record<string, any>
}

export interface ConnectionsStory {
  id: string
  title: string
  memory_ids: string[]
  start_time: string | null
  end_time: string | null
  tags: string[]
  memory_count: number
}

export interface ConnectionsProject {
  name: string
  memory_ids: string[]
  memory_count: number
}

export interface ConnectionsResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_memories: number
  stories?: ConnectionsStory[]
  projects?: ConnectionsProject[]
}

// ─── Related Memories (GET /memories/{id}/related) ───────────────────────────
//
// Backend returns: { memory_id, related: RelatedMemoryFull[] }
// Each RelatedMemoryFull has: memory_id, title, score, rel_type, explanation
// (summary and timestamp are optional additions populated by the enriched backend)

export interface RelatedMemoryFull {
  memory_id: string
  title: string | null
  score: number
  /** The backend field name is rel_type (a RelationshipType enum value) */
  rel_type: string
  explanation: string | null
  summary?: string | null
  timestamp?: string | null
}

// ─── API Client ──────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (e) {
    console.error(`GET ${path} failed:`, e)
    return null
  }
}

async function post<T>(path: string, body: unknown): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (e) {
    console.error(`POST ${path} failed:`, e)
    return null
  }
}

export const api = {
  // Memories
  getMemories: (params?: { limit?: number; skip?: number }) => {
    const qs = new URLSearchParams()
    if (params?.limit) qs.set("limit", String(params.limit))
    if (params?.skip) qs.set("skip", String(params.skip))
    return get<Memory[]>(`/memories?${qs}`)
  },

  getMemory: (id: string) => get<Memory>(`/memories/${id}`),

  getRelatedMemories: (id: string) =>
    get<{ memory_id: string; related: RelatedMemoryFull[] }>(`/memories/${id}/related`),

  // Insights
  getInsights: () => get<InsightStats>("/insights"),

  // Timeline
  getTimeline: (params?: { limit?: number; skip?: number }) => {
    const qs = new URLSearchParams()
    if (params?.limit) qs.set("limit", String(params.limit))
    if (params?.skip) qs.set("skip", String(params.skip))
    return get<Memory[]>(`/timeline?${qs}`)
  },

  // Search — GET with q param (returns SearchResponse with SearchResult[] items)
  searchMemories: (params: {
    q: string
    limit?: number
    source_type?: string
    date_from?: string
    date_to?: string
  }) => {
    const qs = new URLSearchParams({ q: params.q })
    if (params.limit) qs.set("limit", String(params.limit))
    if (params.source_type) qs.set("source_type", params.source_type)
    if (params.date_from) qs.set("date_from", params.date_from)
    if (params.date_to) qs.set("date_to", params.date_to)
    return get<SearchResponse>(`/search?${qs}`)
  },

  // Search — POST hybrid
  searchHybrid: (body: { q: string; limit?: number; source_type?: string; date_from?: string; date_to?: string }) =>
    post<SearchResponse>("/search/hybrid", body),

  // Connections
  getConnections: () => get<ConnectionsResponse>("/connections"),

  // Ingest
  uploadFile: async (file: File): Promise<IngestResponse | null> => {
    try {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        body: form
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      return await res.json()
    } catch (e) {
      console.error("Upload failed:", e)
      throw e
    }
  },

  getIngestStatus: (id: string) =>
    get<IngestStatusResponse>(`/ingest/${id}`),

  // Screenshot image URL helper — uses absolute base so images load correctly
  screenshotUrl: (id: string) => `http://localhost:8000/api/v1/screenshots/${id}/image`,

  // Chat
  chat: (message: string, context_memory_ids?: string[]) =>
    post<ChatResponse>("/chat", { message, context_memory_ids })
}
