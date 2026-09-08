import { useEffect, useState } from "react"
import { format } from "date-fns"
import { useNavigate } from "react-router-dom"
import { api, Memory, InsightStats } from "@/services/api"
import { Activity, Clock, Layers, Hash, Upload } from "lucide-react"
import UploadModal from "@/components/upload/UploadModal"

export default function Overview() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [insights, setInsights] = useState<InsightStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null) // Fix 4.4
  const navigate = useNavigate()

  const fetchData = async () => {
    setLoading(true)
    const [mems, stats] = await Promise.all([
      api.getMemories({ limit: 5 }),
      api.getInsights()
    ])
    setMemories(mems || [])
    setInsights(stats)
    setLoading(false)
  }

  useEffect(() => { fetchData() }, [])

  // Fix 4.4: real backend health check
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/health')
        setBackendOnline(res.ok)
      } catch {
        setBackendOnline(false)
      }
    }
    check()
    const interval = setInterval(check, 30_000) // re-check every 30s
    return () => clearInterval(interval)
  }, [])

  const today = format(new Date(), "EEEE, MMMM do")

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="page-date">{today}</p>
          <h1 className="page-title letterpress">Good morning.</h1>
          <p className="page-subtitle" style={{ maxWidth: '480px' }}>
            Here is a summary of what your digital memory captured recently.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-secondary" onClick={() => setShowUpload(true)}>
            <Upload size={15} />
            Capture
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/search')}>
            Search Memory
          </button>
        </div>
      </div>

      <div className="overview-grid">
        {/* Left: Recent Memories */}
        <div>
          <div className="section-header">
            <h2 className="section-title">Recent Activity</h2>
            <a href="/memories" className="section-link">View all →</a>
          </div>

          <div className="memory-card-list">
            {loading ? (
              [1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: '120px' }}></div>)
            ) : memories.length > 0 ? (
              memories.map(memory => (
                <div
                  key={memory.id}
                  className="memory-card-row"
                  onClick={() => navigate(`/memories/${memory.id}`)}
                >
                  <div className="memory-card-thumb" style={{ minHeight: '110px' }}>
                    {memory.screenshot?.imageUrl
                      ? <img src={memory.screenshot.imageUrl} alt={memory.content?.title} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      : <Layers size={28} color="#D1D5DB" />
                    }
                  </div>
                  <div className="memory-card-body">
                    <div className="memory-card-meta">
                      <Clock size={13} />
                      <span>{format(new Date(memory.timestamp || new Date()), "h:mm a")}</span>
                      <span>•</span>
                      <span style={{ fontWeight: 600 }}>{memory.source?.app || 'Unknown'}</span>
                    </div>
                    <div className="memory-card-title">{memory.content?.title || 'Untitled'}</div>
                    <div className="memory-card-summary">{memory.content?.summary}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="card" style={{ padding: '40px', textAlign: 'center', border: '1.5px dashed #E5E5E5', background: 'transparent' }}>
                <p style={{ color: 'var(--secondary-text)', marginBottom: '16px' }}>No memories yet. Upload your first screenshot!</p>
                <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
                  <Upload size={15} /> Upload Screenshot
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right: Widgets */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={18} color="var(--accent)" />
                System Status
              </div>
            </div>
            <div className="card-content">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--secondary-text)' }}>Total Memories</span>
                  <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.4rem', fontWeight: 700 }}>
                    {insights?.total_memories ?? '—'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--secondary-text)' }}>Entities Tracked</span>
                  <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.4rem', fontWeight: 700 }}>
                    {insights?.total_entities ?? '—'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--secondary-text)' }}>Pipeline</span>
                  {/* Fix 4.4: real status badge */}
                  {backendOnline === null
                    ? <span className="badge badge-secondary">Checking…</span>
                    : backendOnline
                    ? <span className="badge badge-success">Online ✓</span>
                    : <span className="badge" style={{ background: '#FEE2E2', color: '#DC2626' }}>Offline ✗</span>
                  }
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Hash size={18} color="var(--accent)" />
                Top Entities
              </div>
            </div>
            <div className="card-content">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {loading ? (
                  <span style={{ fontSize: '0.875rem', color: 'var(--secondary-text)' }}>Loading...</span>
                ) : insights?.top_entities && insights.top_entities.length > 0 ? (
                  insights.top_entities.map((entity, i) => (
                    <span key={i} className="badge badge-secondary">
                      {entity.name}
                      <span style={{ marginLeft: '4px', opacity: 0.5, fontSize: '0.7rem' }}>{entity.count}</span>
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.875rem', color: 'var(--secondary-text)' }}>No entities yet.</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSuccess={() => {
            setShowUpload(false)
            fetchData()
          }}
        />
      )}
    </div>
  )
}
