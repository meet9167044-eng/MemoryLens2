import { useEffect, useState } from "react"
import { api, InsightStats } from "@/services/api"
import { TrendingUp, Zap, FileText, Share2 } from "lucide-react"
import { EmptyLibrary } from "@/components/ui/EmptyLibrary"

function formatConfidence(avg: number | null | undefined): { label: string; width: number } | null {
  if (avg == null) return null
  const pct = avg <= 1 ? avg * 100 : avg
  return { label: `${pct.toFixed(1)}%`, width: Math.max(0, Math.min(100, pct)) }
}

export default function Insights() {
  const [insights, setInsights] = useState<InsightStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      const stats = await api.getInsights()
      setInsights(stats)
      setLoading(false)
    }
    fetchData()
  }, [])

  const ocr = formatConfidence(insights?.avg_confidence)
  const maxDay = Math.max(1, ...(insights?.activity_by_day || []).map(d => d.count))
  const empty = !loading && (insights?.total_memories ?? 0) === 0

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title letterpress">System Insights</h1>
          <p className="page-subtitle">Analytics on your digital memory capture and processing pipeline.</p>
        </div>
        <div className="live-indicator">
          <div className="live-dot"></div>
          Live Processing
        </div>
      </div>

      {loading ? (
        <div className="stats-row">
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: "140px" }}></div>
          ))}
        </div>
      ) : empty ? (
        <EmptyLibrary title="No insights yet" />
      ) : (
        <>
          <div className="stats-row">
            <div className="stat-card">
              <div className="stat-label"><FileText size={14} /> Total Captured</div>
              <div className="stat-value">{insights?.total_memories || 0}</div>
              <div className="stat-sub">
                <TrendingUp size={13} /> {insights?.recent_activity_count ?? 0} in the last 7 days
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label"><Share2 size={14} /> Entities Extracted</div>
              <div className="stat-value">{insights?.total_entities || 0}</div>
              <div style={{ fontSize: "0.8rem", color: "var(--secondary-text)", marginTop: "8px" }}>
                Across uploaded memories
              </div>
            </div>
            <div className="stat-card" style={{ background: "linear-gradient(135deg, #EFF6FF 0%, #fff 100%)", borderColor: "#DBEAFE" }}>
              <div className="stat-label" style={{ color: "#1D4ED8" }}><Zap size={14} /> OCR Confidence</div>
              {ocr ? (
                <>
                  <div className="stat-value" style={{ color: "#1e40af" }}>{ocr.label}</div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${ocr.width}%` }}></div>
                  </div>
                </>
              ) : (
                <>
                  <div className="stat-value" style={{ color: "#1e40af", fontSize: "1.2rem" }}>No data</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--secondary-text)", marginTop: "8px" }}>
                    Confidence appears after the pipeline scores a memory.
                  </div>
                </>
              )}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginTop: "8px" }}>
            <div className="card">
              <div className="card-header">
                <div className="card-title">Top Semantic Tags</div>
                <div className="card-desc">Most frequently detected topics across all memories.</div>
              </div>
              <div className="card-content">
                {insights?.top_tags?.length ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                    {insights.top_tags.map((tag, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span style={{ color: "#9CA3AF", fontFamily: "monospace", fontSize: "0.8rem", width: "16px" }}>{i + 1}</span>
                          <span style={{ fontWeight: 500, fontSize: "0.9rem" }}>{tag.name}</span>
                        </div>
                        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--secondary-text)" }}>{tag.count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: "24px", color: "var(--secondary-text)", fontSize: "0.875rem" }}>
                    No tag data available yet.
                  </div>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title">Pipeline Activity</div>
                <div className="card-desc">Memories created over the last 7 days.</div>
              </div>
              <div className="card-content" style={{ minHeight: "200px" }}>
                {insights?.activity_by_day?.length ? (
                  <div style={{ display: "flex", alignItems: "flex-end", gap: "8px", height: "180px", paddingTop: "12px" }}>
                    {insights.activity_by_day.map(day => (
                      <div key={day.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", height: "100%", justifyContent: "flex-end" }}>
                        <span style={{ fontSize: "0.7rem", color: "var(--secondary-text)" }}>{day.count}</span>
                        <div
                          title={`${day.date}: ${day.count}`}
                          style={{
                            width: "100%",
                            maxWidth: "28px",
                            height: `${Math.max(4, (day.count / maxDay) * 140)}px`,
                            background: day.count ? "#3B82F6" : "#E5E7EB",
                            borderRadius: "4px 4px 0 0",
                          }}
                        />
                        <span style={{ fontSize: "0.65rem", color: "var(--secondary-text)" }}>
                          {day.date.slice(5)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: "24px", color: "var(--secondary-text)", fontSize: "0.875rem" }}>
                    No activity in the last 7 days.
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
