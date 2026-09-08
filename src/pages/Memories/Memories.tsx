import { useEffect, useState } from "react"
import { format } from "date-fns"
import { useNavigate } from "react-router-dom"
import { api, Memory } from "@/services/api"
import { Clock, Layers, Filter, Trash2, X, ChevronDown } from "lucide-react"
import UploadModal from "@/components/upload/UploadModal"
import { EmptyLibrary, UploadCta } from "@/components/ui/EmptyLibrary"

// imageUrl from backend is relative (/api/v1/screenshots/…/image) — Vite proxy handles it

const SOURCE_TYPES = ["desktop", "browser", "terminal", "document", "other"] as const

export default function Memories() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [skip, setSkip] = useState(0)
  const [showUpload, setShowUpload] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  // Fix 4.1: filter state
  const [showFilter, setShowFilter] = useState(false)
  const [filterSource, setFilterSource] = useState<string>("")
  const [filterText, setFilterText] = useState("")
  const navigate = useNavigate()

  const LIMIT = 24

  const fetchData = async (reset = true) => {
    const newSkip = reset ? 0 : skip
    if (reset) setLoading(true)
    else setLoadingMore(true)

    const data = await api.getMemories({ limit: LIMIT, skip: newSkip }) || []
    if (reset) {
      setMemories(data)
      setSkip(LIMIT)
    } else {
      setMemories(prev => [...prev, ...data])
      setSkip(prev => prev + LIMIT)
    }
    setHasMore(data.length === LIMIT)
    setLoading(false)
    setLoadingMore(false)
  }

  useEffect(() => { fetchData(true) }, [])

  // Fix 2.3: delete a memory card with confirmation
  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!confirm("Delete this memory? This cannot be undone.")) return
    setDeleting(id)
    const ok = await api.deleteMemory(id)
    if (ok) setMemories(prev => prev.filter(m => m.id !== id))
    setDeleting(null)
  }

  // Fix 4.1: client-side filter on loaded memories
  const filtered = memories.filter(m => {
    if (filterSource && m.source?.type !== filterSource) return false
    if (filterText) {
      const q = filterText.toLowerCase()
      const title = (m.content?.title || "").toLowerCase()
      const summary = (m.content?.summary || "").toLowerCase()
      const tags = (m.tags || []).join(" ").toLowerCase()
      if (!title.includes(q) && !summary.includes(q) && !tags.includes(q)) return false
    }
    return true
  })

  const activeFilters = [filterSource, filterText].filter(Boolean).length

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title letterpress">Memory Explorer</h1>
          <p className="page-subtitle">Browse and filter your captured digital history.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          {/* Fix 4.1: filter toggle button */}
          <button
            className={`btn ${showFilter ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowFilter(f => !f)}
          >
            <Filter size={15} />
            Filter {activeFilters > 0 && `(${activeFilters})`}
            <ChevronDown size={13} style={{ transform: showFilter ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
          </button>
          <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
            + Upload
          </button>
        </div>
      </div>

      {/* Fix 4.1: Filter panel */}
      {showFilter && (
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border)',
          borderRadius: '12px', padding: '16px 20px', marginBottom: '20px',
          display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end'
        }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--secondary-text)', display: 'block', marginBottom: '6px' }}>
              SEARCH
            </label>
            <input
              type="text"
              placeholder="Title, summary or tag…"
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              style={{
                width: '100%', padding: '8px 12px', borderRadius: '8px',
                border: '1px solid var(--border)', fontSize: '0.875rem',
                background: 'var(--bg)', color: 'var(--primary-text)', outline: 'none'
              }}
            />
          </div>
          <div style={{ minWidth: '160px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--secondary-text)', display: 'block', marginBottom: '6px' }}>
              SOURCE TYPE
            </label>
            <select
              value={filterSource}
              onChange={e => setFilterSource(e.target.value)}
              style={{
                width: '100%', padding: '8px 12px', borderRadius: '8px',
                border: '1px solid var(--border)', fontSize: '0.875rem',
                background: 'var(--bg)', color: 'var(--primary-text)', cursor: 'pointer'
              }}
            >
              <option value="">All types</option>
              {SOURCE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
            </select>
          </div>
          {activeFilters > 0 && (
            <button
              className="btn btn-secondary"
              onClick={() => { setFilterSource(""); setFilterText("") }}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <X size={13} /> Clear
            </button>
          )}
          <span style={{ fontSize: '0.8rem', color: 'var(--secondary-text)', alignSelf: 'center' }}>
            {filtered.length} of {memories.length} shown
          </span>
        </div>
      )}

      {loading ? (
        <div className="memory-grid">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="skeleton" style={{ height: '280px' }}></div>
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <>
          <div className="memory-grid">
            {filtered.map(memory => (
              <div key={memory.id} className="memory-card-grid" onClick={() => navigate(`/memories/${memory.id}`)}>
                <div className="memory-card-grid-thumb">
                  {memory.screenshot?.imageUrl ? (
                    <img
                      src={memory.screenshot?.imageUrl}
                      alt={memory.content?.title}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                  ) : (
                    <Layers size={28} color="#D1D5DB" />
                  )}
                  <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span className="badge badge-dark">{memory.source?.app || 'App'}</span>
                    <button
                      onClick={e => handleDelete(e, memory.id)}
                      disabled={deleting === memory.id}
                      title="Delete memory"
                      style={{
                        background: 'rgba(220,38,38,0.85)', border: 'none', borderRadius: '6px',
                        padding: '4px 6px', cursor: 'pointer', color: '#fff',
                        display: 'flex', alignItems: 'center', opacity: deleting === memory.id ? 0.5 : 1,
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
                <div className="memory-card-grid-body">
                  <div className="memory-card-meta">
                    <Clock size={12} />
                    <span>{format(new Date(memory.timestamp || new Date()), "MMM d, h:mm a")}</span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '8px', lineHeight: 1.3, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {memory.content?.title || 'Untitled'}
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--secondary-text)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', flex: 1 }}>
                    {memory.content?.summary}
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '14px' }}>
                    {memory.tags?.slice(0, 3).map((tag, i) => (
                      <span key={i} className="tag-pill">#{tag}</span>
                    ))}
                    {memory.tags && memory.tags.length > 3 && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--secondary-text)' }}>+{memory.tags.length - 3}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Fix 4.2: Load more button */}
          {hasMore && !filterSource && !filterText && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '32px' }}>
              <button
                className="btn btn-secondary"
                onClick={() => fetchData(false)}
                disabled={loadingMore}
                style={{ minWidth: '160px', justifyContent: 'center' }}
              >
                {loadingMore ? 'Loading…' : `Load more`}
              </button>
            </div>
          )}
        </>
      ) : memories.length > 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--secondary-text)' }}>
          No memories match your filters.
          <button className="btn btn-secondary" style={{ marginLeft: '12px' }} onClick={() => { setFilterSource(""); setFilterText("") }}>
            Clear filters
          </button>
        </div>
      ) : (
        <EmptyLibrary
          title="Upload to get started"
          icon={<Layers size={28} />}
          action={<UploadCta onClick={() => setShowUpload(true)} />}
        />
      )}

      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onSuccess={() => { setShowUpload(false); fetchData(true) }} />
      )}
    </div>
  )
}
