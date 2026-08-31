import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { format, subDays, eachDayOfInterval, isSameDay } from "date-fns"
import { api, Memory } from "@/services/api"
import { Clock, Monitor, Calendar } from "lucide-react"

export default function Timeline() {
  const [timelineItems, setTimelineItems] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getTimeline({ limit: 200 }).then(data => {
      setTimelineItems(data || [])
      setLoading(false)
    })
  }, [])

  // Group by exact date string for the list
  const grouped = timelineItems.reduce((acc, item) => {
    const d = format(new Date(item.timestamp || new Date()), "MMMM d, yyyy")
    if (!acc[d]) acc[d] = []
    acc[d].push(item)
    return acc
  }, {} as Record<string, Memory[]>)

  // Heatmap logic (last 84 days = 12 weeks)
  const today = new Date()
  const startDate = subDays(today, 83)
  const days = eachDayOfInterval({ start: startDate, end: today })
  
  const getIntensity = (date: Date) => {
    const count = timelineItems.filter(m => isSameDay(new Date(m.timestamp || new Date()), date)).length
    if (count === 0) return "var(--bg)"
    if (count <= 2) return "#DBEAFE" // light blue
    if (count <= 5) return "#93C5FD"
    if (count <= 10) return "#3B82F6"
    return "#1D4ED8" // dark blue
  }

  const getCount = (date: Date) => {
    return timelineItems.filter(m => isSameDay(new Date(m.timestamp || new Date()), date)).length
  }

  return (
    <div style={{ maxWidth: '860px', margin: '0 auto' }}>
      <div className="page-header" style={{ marginBottom: '40px' }}>
        <div>
          <h1 className="page-title letterpress">Timeline</h1>
          <p className="page-subtitle">Your digital activity across time, in chronological order.</p>
        </div>
      </div>

      {/* HEATMAP */}
      {!loading && timelineItems.length > 0 && (
        <div className="card" style={{ padding: '24px', marginBottom: '48px', overflowX: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Calendar size={18} color="var(--accent)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--primary-text)', margin: 0 }}>Activity Heatmap (Last 12 Weeks)</h3>
          </div>
          
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(12, 1fr)', 
            gridAutoFlow: 'column', 
            gridTemplateRows: 'repeat(7, 1fr)', 
            gap: '4px',
            width: 'max-content' 
          }}>
            {days.map((day, i) => {
              const count = getCount(day)
              return (
                <div 
                  key={i} 
                  title={`${format(day, 'MMM d, yyyy')}: ${count} memories`}
                  style={{ 
                    width: '14px', height: '14px', 
                    backgroundColor: getIntensity(day),
                    borderRadius: '3px',
                    border: '1px solid rgba(0,0,0,0.05)',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    // Scroll to date if it exists
                    const dateStr = format(day, "MMMM d, yyyy")
                    const el = document.getElementById(`date-${dateStr}`)
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  }}
                />
              )
            })}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px', fontSize: '0.75rem', color: 'var(--secondary-text)' }}>
            <span>Less</span>
            <div style={{ width: '12px', height: '12px', background: 'var(--bg)', borderRadius: '2px' }} />
            <div style={{ width: '12px', height: '12px', background: '#DBEAFE', borderRadius: '2px' }} />
            <div style={{ width: '12px', height: '12px', background: '#93C5FD', borderRadius: '2px' }} />
            <div style={{ width: '12px', height: '12px', background: '#3B82F6', borderRadius: '2px' }} />
            <div style={{ width: '12px', height: '12px', background: '#1D4ED8', borderRadius: '2px' }} />
            <span>More</span>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '36px' }}>
          {[1, 2].map(i => (
            <div key={i}>
              <div className="skeleton" style={{ height: '28px', width: '200px', marginBottom: '20px' }}></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', paddingLeft: '40px' }}>
                {[1, 2].map(j => <div key={j} className="skeleton" style={{ height: '100px' }}></div>)}
              </div>
            </div>
          ))}
        </div>
      ) : Object.keys(grouped).length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '48px' }}>
          {Object.entries(grouped).map(([date, mems]) => (
            <div key={date} id={`date-${date}`} className="timeline-section" style={{ scrollMarginTop: '80px' }}>
              <div className="timeline-date">{date}</div>
              <div className="timeline-list">
                {mems.map((memory) => (
                  <div key={memory.id} className="timeline-item" onClick={() => navigate(`/memories/${memory.id}`)}>
                    <div className="timeline-dot"></div>
                    <div className="memory-card-row">
                      {memory.screenshot?.imageUrl && (
                        <div className="memory-card-thumb" style={{ width: '120px', minHeight: '90px' }}>
                          <img
                            src={memory.screenshot.imageUrl}
                            alt=""
                            onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                          />
                        </div>
                      )}
                      <div className="memory-card-body">
                        <div className="memory-card-meta">
                          <Clock size={12} />
                          <span>{format(new Date(memory.timestamp || new Date()), "h:mm a")}</span>
                          <span>•</span>
                          <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                            <Monitor size={12} style={{ display: 'inline', marginRight: '3px' }} />
                            {memory.source?.app || 'Unknown'}
                          </span>
                        </div>
                        <div className="memory-card-title">{memory.content?.title || 'Untitled'}</div>
                        <div className="memory-card-summary">{memory.content?.summary}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ height: '50vh' }}>
          <div className="empty-icon"><Clock size={28} /></div>
          <div className="empty-title">No timeline events</div>
          <p>Capture some memories to build your timeline.</p>
        </div>
      )}
    </div>
  )
}