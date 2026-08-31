import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { format } from "date-fns"
import { api, Memory, RelatedMemoryFull } from "@/services/api"
import { ArrowLeft, Clock, Monitor, Tag, AlignLeft, Layers, Network } from "lucide-react"

export default function MemoryDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [memory, setMemory] = useState<Memory | null>(null)
  const [related, setRelated] = useState<RelatedMemoryFull[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.getMemory(id),
      api.getRelatedMemories(id)
    ]).then(([mem, rel]) => {
      setMemory(mem)
      setRelated(rel?.related || [])
      setLoading(false)
    })
  }, [id])

  if (loading) {
    return (
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        <div className="skeleton" style={{ height: '32px', width: '80px', marginBottom: '24px' }}></div>
        <div className="skeleton" style={{ height: '48px', width: '70%', marginBottom: '16px' }}></div>
        <div className="skeleton" style={{ height: '400px', borderRadius: '12px', marginTop: '32px' }}></div>
      </div>
    )
  }

  if (!memory) {
    return (
      <div className="empty-state" style={{ height: '60vh' }}>
        <div className="empty-icon"><Layers size={28} /></div>
        <div className="empty-title">Memory not found</div>
        <button className="btn btn-secondary" style={{ marginTop: '16px' }} onClick={() => navigate("/memories")}>
          Return to Memories
        </button>
      </div>
    )
  }

  const imgUrl = memory.screenshot?.imageUrl || null

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', paddingBottom: '80px', display: 'flex', gap: '40px', alignItems: 'flex-start' }}>
      
      {/* LEFT COLUMN: Main Memory Detail */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <button className="back-btn" onClick={() => navigate(-1)}>
          <ArrowLeft size={16} />
          Back
        </button>

        {/* Title */}
        <div style={{ marginBottom: '36px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.8rem', color: 'var(--secondary-text)', marginBottom: '12px', flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Clock size={14} />
              {format(new Date(memory.timestamp || new Date()), "MMMM d, yyyy 'at' h:mm a")}
            </span>
            <span>•</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Monitor size={14} /> {memory.source?.app || 'Unknown App'}
            </span>
            <span>•</span>
            <span className={`badge badge-${(memory.metadata?.confidence || 0) > 0.9 ? 'success' : 'outline'}`}>
              {Math.round((memory.metadata?.confidence || 0) * 100)}% confidence
            </span>
          </div>
          <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: '2.2rem', fontWeight: 700, color: 'var(--primary-text)', lineHeight: 1.2, letterSpacing: '-0.02em', marginBottom: '12px' }}>
            {memory.content?.title || 'Untitled Memory'}
          </h1>
          <p style={{ fontSize: '1rem', color: 'var(--secondary-text)', lineHeight: 1.7, maxWidth: '680px' }}>
            {memory.content?.summary}
          </p>
        </div>

        {/* Detail grid (Image + Metadata) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          {/* Evidence */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Monitor size={17} color="var(--accent)" />
              <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.1rem', fontWeight: 600 }}>Evidence</span>
            </div>
            <div className="detail-evidence">
              {imgUrl ? (
                <img src={imgUrl} alt={memory.content?.title} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              ) : (
                <div className="empty-state" style={{ height: '200px' }}><Layers size={36} color="#D1D5DB" /></div>
              )}
            </div>
          </div>

          {/* OCR */}
          {memory.content?.ocrText && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <AlignLeft size={17} color="var(--accent)" />
                <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.1rem', fontWeight: 600 }}>Captured Text</span>
              </div>
              <div className="detail-ocr"><pre>{memory.content.ocrText}</pre></div>
            </div>
          )}

          {/* Metadata Grid (Tags + Entities) */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            {/* Tags */}
            <div className="card">
              <div className="card-header">
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Tag size={16} color="var(--accent)" />
                  Metadata
                </div>
              </div>
              <div className="card-content">
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--secondary-text)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '10px' }}>Tags</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {memory.tags?.length
                      ? memory.tags.map((tag, i) => <span key={i} className="badge badge-secondary">#{tag}</span>)
                      : <span style={{ fontSize: '0.85rem', color: 'var(--secondary-text)' }}>No tags</span>
                    }
                  </div>
                </div>
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--secondary-text)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '10px' }}>Source Type</div>
                  <span className="badge badge-accent">{memory.metadata?.contentType || 'screenshot'}</span>
                </div>
              </div>
            </div>

            {/* Entities */}
            <div className="card">
              <div className="card-header">
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Tag size={16} color="var(--accent)" />
                  Identified Entities
                </div>
              </div>
              <div className="card-content">
                {memory.entities?.length ? (
                  <div>
                    {memory.entities.map((ent, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: i < memory.entities.length - 1 ? '1px solid var(--border)' : 'none' }}>
                        <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>{ent.name}</span>
                        <span className="badge badge-outline" style={{ fontSize: '0.7rem' }}>{ent.type}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span style={{ fontSize: '0.875rem', color: 'var(--secondary-text)' }}>No entities detected</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR: Related Screenshots (Phase G) */}
      <div style={{ width: '320px', flexShrink: 0, position: 'sticky', top: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
          <Network size={18} color="var(--accent)" />
          <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', fontWeight: 600, color: 'var(--primary-text)' }}>
            Related Screenshots
          </h2>
          {related.length > 0 && <span className="badge badge-outline">{related.length}</span>}
        </div>
        
        {related.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {related.map((rel, i) => (
              <div
                key={i}
                onClick={() => navigate(`/memories/${rel.memory_id}`)}
                style={{ 
                  background: 'white', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px',
                  cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
                }}
                onMouseOver={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                onMouseOut={e => e.currentTarget.style.borderColor = 'var(--border)'}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span className="badge badge-accent" style={{ fontSize: '0.65rem' }}>
                    {(rel.rel_type || '').replace(/_/g, ' ')}
                  </span>
                  {rel.score > 0 && (
                    <span style={{ fontSize: '0.7rem', color: 'var(--secondary-text)', fontWeight: 600 }}>
                      {Math.round(rel.score * 100)}%
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--primary-text)', marginBottom: '6px', lineHeight: 1.3 }}>
                  {rel.title || 'Untitled Memory'}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--secondary-text)', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {rel.explanation || rel.summary}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: '24px', textAlign: 'center', background: 'var(--bg)', borderRadius: '12px', border: '1px dashed var(--border)' }}>
            <Network size={24} color="#9CA3AF" style={{ margin: '0 auto 12px' }} />
            <div style={{ fontSize: '0.85rem', color: 'var(--secondary-text)' }}>No related memories found.</div>
          </div>
        )}
      </div>

    </div>
  )
}