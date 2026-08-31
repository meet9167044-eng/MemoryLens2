import { useEffect, useState } from "react"
import { Settings as SettingsIcon, FolderOpen, Play, Square, RefreshCw, Upload, CheckCircle, AlertCircle, Clock } from "lucide-react"

const API_BASE = "http://localhost:8000/api/v1"

interface WatchStatus {
  running: boolean
  watch_path: string | null
  message: string
}

interface BulkResult {
  accepted: { filename: string; screenshot_id: string }[]
  rejected: { filename: string; reason: string }[]
  duplicates: { filename: string; screenshot_id: string }[]
  summary: { total: number; accepted_count: number; rejected_count: number; duplicate_count: number }
}

async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`)
    if (!res.ok) return null
    return res.json()
  } catch { return null }
}

async function apiPost<T>(path: string, body?: object): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    })
    return res.json()
  } catch { return null }
}

export default function Settings() {
  const [watchStatus, setWatchStatus] = useState<WatchStatus | null>(null)
  const [watchPath, setWatchPath] = useState("")
  const [watchLoading, setWatchLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null)

  const [bulkFiles, setBulkFiles] = useState<FileList | null>(null)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [bulkResult, setBulkResult] = useState<BulkResult | null>(null)

  async function refreshStatus() {
    const s = await apiGet<WatchStatus>("/watch")
    if (s) {
      setWatchStatus(s)
      if (s.watch_path) setWatchPath(s.watch_path)
    }
  }

  useEffect(() => { refreshStatus() }, [])

  async function handleStart() {
    if (!watchPath.trim()) {
      setStatusMsg({ type: "err", text: "Please enter a folder path to watch." })
      return
    }
    setWatchLoading(true)
    setStatusMsg(null)
    const res = await apiPost<WatchStatus>("/watch/start", { path: watchPath.trim(), recursive: false })
    if (res) {
      setWatchStatus(res)
      setStatusMsg({ type: res.running ? "ok" : "err", text: res.message })
    }
    setWatchLoading(false)
  }

  async function handleStop() {
    setWatchLoading(true)
    setStatusMsg(null)
    const res = await apiPost<WatchStatus>("/watch/stop")
    if (res) {
      setWatchStatus(res)
      setStatusMsg({ type: "ok", text: res.message })
    }
    setWatchLoading(false)
  }

  async function handleBulkImport() {
    if (!bulkFiles || bulkFiles.length === 0) return
    setBulkLoading(true)
    setBulkResult(null)
    const form = new FormData()
    for (let i = 0; i < bulkFiles.length; i++) form.append("files", bulkFiles[i])
    try {
      const res = await fetch(`${API_BASE}/ingest/bulk`, { method: "POST", body: form })
      const data: BulkResult = await res.json()
      setBulkResult(data)
    } catch (e) {
      console.error(e)
    }
    setBulkLoading(false)
  }

  const isRunning = watchStatus?.running ?? false

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title letterpress">Settings</h1>
          <p className="page-subtitle">Configure auto-capture and manage imports.</p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>

        {/* ── Auto-Capture Section ── */}
        <div className="card" style={{ padding: "28px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
            <div className="connection-icon" style={{ width: "40px", height: "40px", flexShrink: 0 }}>
              <FolderOpen size={18} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "var(--primary-text)" }}>
                Auto-Capture
              </h2>
              <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--secondary-text)" }}>
                Watch a folder and automatically ingest new screenshots.
              </p>
            </div>
            {/* Toggle indicator */}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "8px" }}>
              <div style={{
                width: "44px", height: "24px", borderRadius: "12px",
                background: isRunning ? "var(--accent)" : "var(--border)",
                position: "relative", transition: "background 0.3s", cursor: "pointer",
                flexShrink: 0,
              }} onClick={isRunning ? handleStop : () => {}}>
                <div style={{
                  position: "absolute", top: "3px",
                  left: isRunning ? "23px" : "3px",
                  width: "18px", height: "18px", borderRadius: "50%",
                  background: "white", transition: "left 0.3s",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                }} />
              </div>
              <span style={{ fontSize: "0.82rem", fontWeight: 600, color: isRunning ? "var(--accent)" : "var(--secondary-text)" }}>
                {isRunning ? "Active" : "Inactive"}
              </span>
            </div>
          </div>

          {/* Status badge */}
          {watchStatus && (
            <div style={{
              display: "flex", alignItems: "center", gap: "8px",
              padding: "10px 14px", borderRadius: "10px",
              background: isRunning ? "#ECFDF5" : "var(--bg)",
              border: `1px solid ${isRunning ? "#6EE7B7" : "var(--border)"}`,
              marginBottom: "20px", fontSize: "0.82rem",
            }}>
              {isRunning
                ? <CheckCircle size={15} color="#10B981" />
                : <Clock size={15} color="var(--secondary-text)" />
              }
              <span style={{ color: isRunning ? "#065F46" : "var(--secondary-text)", fontWeight: 500 }}>
                {watchStatus.message}
              </span>
              <button id="settings-refresh-btn" onClick={refreshStatus} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "var(--secondary-text)", padding: "2px" }}>
                <RefreshCw size={13} />
              </button>
            </div>
          )}

          {/* Path input */}
          <div style={{ display: "flex", gap: "10px", marginBottom: "16px" }}>
            <input
              id="settings-watch-path"
              type="text"
              value={watchPath}
              onChange={e => setWatchPath(e.target.value)}
              placeholder="e.g. C:\Users\YourName\Screenshots"
              disabled={isRunning}
              style={{
                flex: 1, padding: "10px 14px", borderRadius: "10px",
                border: "1.5px solid var(--border)", background: isRunning ? "var(--bg)" : "white",
                fontSize: "0.88rem", color: "var(--primary-text)",
                outline: "none", fontFamily: "var(--font-mono, monospace)",
              }}
            />
          </div>

          {/* Start / Stop buttons */}
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              id="settings-start-watch-btn"
              onClick={handleStart}
              disabled={isRunning || watchLoading}
              className="btn-primary"
              style={{ display: "flex", alignItems: "center", gap: "6px", opacity: isRunning ? 0.5 : 1 }}
            >
              <Play size={15} />
              Start Watching
            </button>
            <button
              id="settings-stop-watch-btn"
              onClick={handleStop}
              disabled={!isRunning || watchLoading}
              style={{
                display: "flex", alignItems: "center", gap: "6px",
                padding: "10px 18px", borderRadius: "10px",
                background: isRunning ? "#FEF2F2" : "var(--bg)",
                border: `1.5px solid ${isRunning ? "#FCA5A5" : "var(--border)"}`,
                color: isRunning ? "#DC2626" : "var(--secondary-text)",
                fontWeight: 600, fontSize: "0.88rem", cursor: isRunning ? "pointer" : "not-allowed",
                transition: "all 0.2s",
              }}
            >
              <Square size={15} />
              Stop Watching
            </button>
          </div>

          {/* Status message */}
          {statusMsg && (
            <div style={{
              marginTop: "14px", padding: "10px 14px", borderRadius: "10px",
              background: statusMsg.type === "ok" ? "#ECFDF5" : "#FEF2F2",
              border: `1px solid ${statusMsg.type === "ok" ? "#6EE7B7" : "#FCA5A5"}`,
              fontSize: "0.82rem", fontWeight: 500,
              color: statusMsg.type === "ok" ? "#065F46" : "#DC2626",
              display: "flex", alignItems: "center", gap: "8px",
            }}>
              {statusMsg.type === "ok"
                ? <CheckCircle size={14} />
                : <AlertCircle size={14} />
              }
              {statusMsg.text}
            </div>
          )}
        </div>

        {/* ── Bulk Import Section ── */}
        <div className="card" style={{ padding: "28px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
            <div className="connection-icon" style={{ width: "40px", height: "40px", flexShrink: 0 }}>
              <Upload size={18} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "var(--primary-text)" }}>
                Bulk Import
              </h2>
              <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--secondary-text)" }}>
                Import multiple screenshots at once (up to 50 files).
              </p>
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px", marginBottom: "16px", alignItems: "center" }}>
            <label
              id="settings-bulk-file-label"
              htmlFor="bulk-file-input"
              style={{
                display: "flex", alignItems: "center", gap: "8px",
                padding: "10px 18px", borderRadius: "10px",
                border: "1.5px dashed var(--border)", background: "var(--bg)",
                cursor: "pointer", fontSize: "0.88rem", color: "var(--secondary-text)",
                fontWeight: 500, transition: "all 0.2s",
              }}
            >
              <FolderOpen size={16} />
              {bulkFiles && bulkFiles.length > 0 ? `${bulkFiles.length} file(s) selected` : "Choose files…"}
            </label>
            <input
              id="bulk-file-input"
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp,image/bmp"
              style={{ display: "none" }}
              onChange={e => setBulkFiles(e.target.files)}
            />
            <button
              id="settings-bulk-import-btn"
              onClick={handleBulkImport}
              disabled={!bulkFiles || bulkFiles.length === 0 || bulkLoading}
              className="btn-primary"
              style={{ display: "flex", alignItems: "center", gap: "6px" }}
            >
              {bulkLoading ? <RefreshCw size={15} style={{ animation: "spin 0.8s linear infinite" }} /> : <Upload size={15} />}
              {bulkLoading ? "Importing…" : "Import"}
            </button>
          </div>

          {/* Bulk result */}
          {bulkResult && (
            <div style={{ marginTop: "16px" }}>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginBottom: "12px" }}>
                {[
                  { label: "Accepted", count: bulkResult.summary.accepted_count, color: "#10B981" },
                  { label: "Duplicates", count: bulkResult.summary.duplicate_count, color: "#F59E0B" },
                  { label: "Rejected", count: bulkResult.summary.rejected_count, color: "#EF4444" },
                ].map(({ label, count, color }) => (
                  <div key={label} style={{
                    display: "flex", alignItems: "center", gap: "6px",
                    padding: "6px 14px", borderRadius: "999px",
                    background: color + "15", border: `1px solid ${color}40`,
                    fontSize: "0.82rem", fontWeight: 600, color,
                  }}>
                    <span style={{ fontWeight: 800, fontSize: "1rem" }}>{count}</span> {label}
                  </div>
                ))}
              </div>
              {bulkResult.rejected.length > 0 && (
                <div style={{ background: "#FEF2F2", borderRadius: "10px", padding: "12px 16px" }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#DC2626", marginBottom: "6px" }}>Rejected files:</div>
                  {bulkResult.rejected.map((r, i) => (
                    <div key={i} style={{ fontSize: "0.78rem", color: "#7F1D1D" }}>
                      {r.filename}: {r.reason}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Info card ── */}
        <div className="card" style={{ padding: "22px", background: "var(--bg)" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
            <SettingsIcon size={18} color="var(--accent)" style={{ flexShrink: 0, marginTop: "2px" }} />
            <div style={{ fontSize: "0.82rem", color: "var(--secondary-text)", lineHeight: 1.7 }}>
              <strong style={{ color: "var(--primary-text)" }}>How Auto-Capture works:</strong><br />
              Set a folder path (e.g. your system Screenshots folder), click Start, and MemoryLens will watch for new images in real-time. Any PNG, JPG, or WEBP file added to that folder is automatically ingested and processed through the full AI pipeline — no manual upload needed.
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}