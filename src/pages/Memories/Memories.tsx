import { useEffect, useState } from "react"
import { format } from "date-fns"
import { useNavigate } from "react-router-dom"
import { api, Memory } from "@/services/api"
import { Clock, Layers, Filter } from "lucide-react"
import UploadModal from "@/components/upload/UploadModal"
import { EmptyLibrary, UploadCta } from "@/components/ui/EmptyLibrary"

// imageUrl from backend is relative (/api/v1/screenshots/…/image) — Vite proxy handles it

export default function Memories() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const navigate = useNavigate()

  const fetchData = async () => {
    setLoading(true)
    const data = await api.getMemories({ limit: 24 })
    setMemories(data || [])
    setLoading(false)
  }

  useEffect(() => { fetchData() }, [])

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title letterpress">Memory Explorer</h1>
          <p className="page-subtitle">Browse and filter your captured digital history.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-secondary">
            <Filter size={15} />
            Filter
          </button>
          <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
            + Upload
          </button>
        </div>
      </div>

      {loading ? (
        <div className="memory-grid">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="skeleton" style={{ height: '280px' }}></div>
          ))}
        </div>
      ) : memories.length > 0 ? (
        <div className="memory-grid">
          {memories.map(memory => (
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
                <div style={{ position: 'absolute', top: '10px', right: '10px' }}>
                  <span className="badge badge-dark">{memory.source?.app || 'App'}</span>
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
      ) : (
        <EmptyLibrary
          title="Upload to get started"
          icon={<Layers size={28} />}
          action={<UploadCta onClick={() => setShowUpload(true)} />}
        />
      )}

      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onSuccess={() => { setShowUpload(false); fetchData() }} />
      )}
    </div>
  )
}
