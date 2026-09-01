import React, { useCallback, useRef, useState } from "react"
import { api } from "@/services/api"
import { Upload, X, CheckCircle, Loader, AlertCircle, FileImage } from "lucide-react"

type UploadState = "idle" | "uploading" | "polling" | "done" | "error"

interface Props {
  onClose: () => void
  onSuccess: () => void
}

const ALLOWED = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"]
const MAX_MB = 50

export default function UploadModal({ onClose, onSuccess }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [state, setState] = useState<UploadState>("idle")
  const [progress, setProgress] = useState<{ name: string; status: string; id?: string }[]>([])
  const [errorMsg, setErrorMsg] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  // ── File validation
  const validateFile = (f: File): string | null => {
    if (!ALLOWED.includes(f.type)) return `"${f.name}" is not a supported image type.`
    if (f.size > MAX_MB * 1024 * 1024) return `"${f.name}" exceeds 50 MB.`
    return null
  }

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return
    const newFiles: File[] = []
    for (const f of Array.from(incoming)) {
      const err = validateFile(f)
      if (err) { setErrorMsg(err); return }
      newFiles.push(f)
    }
    setFiles(prev => [...prev, ...newFiles])
    setErrorMsg("")
  }

  // ── Drag handlers
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    addFiles(e.dataTransfer.files)
  }, [])

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = () => setDragOver(false)

  // ── Upload
  const handleUpload = async () => {
    if (!files.length) return
    setState("uploading")
    setProgress(files.map(f => ({ name: f.name, status: "Uploading…" })))

    const results: { id: string; name: string }[] = []

    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      try {
        const res = await api.uploadFile(f)
        if (!res) throw new Error("No response from server")
        results.push({ id: res.screenshot_id, name: f.name })
        setProgress(prev => prev.map((p, idx) => idx === i ? { ...p, status: "Processing…", id: res.screenshot_id } : p))
      } catch (err: any) {
        setProgress(prev => prev.map((p, idx) => idx === i ? { ...p, status: `Failed: ${err.message}` } : p))
      }
    }

    // Poll status for each uploaded file
    if (results.length > 0) {
      setState("polling")
      await pollStatuses(results)
    } else {
      setState("error")
      setErrorMsg("All uploads failed. Make sure the backend is running.")
    }
  }

  const pollStatuses = async (items: { id: string; name: string }[]) => {
    const maxAttempts = 20
    let attempts = 0

    while (attempts < maxAttempts) {
      await new Promise(r => setTimeout(r, 2000))
      attempts++

      const allDone = await Promise.all(
        items.map(async ({ id }) => {
          const status = await api.getIngestStatus(id)
          const statusValue = status?.status?.toLowerCase() || "processing"
          const stageValue = status?.stage || ""
          const label = statusValue === "completed" ? "✓ Done" : (stageValue ? `Processing (${stageValue})` : statusValue)
          setProgress(prev =>
            prev.map(p => p.id === id ? { ...p, status: label } : p)
          )
          return statusValue === "completed" || statusValue === "failed"
        })
      )

      if (allDone.every(Boolean)) break
    }

    setState("done")
    setTimeout(() => onSuccess(), 1500)
  }

  const removeFile = (idx: number) => setFiles(prev => prev.filter((_, i) => i !== idx))

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {/* Backdrop */}
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(4px)' }}
        onClick={state === "idle" ? onClose : undefined}
      />

      {/* Modal */}
      <div style={{
        position: 'relative',
        background: '#fff',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '540px',
        margin: '0 20px',
        boxShadow: '0 25px 60px rgba(0,0,0,0.2)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{ padding: '24px 28px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', fontWeight: 700, color: 'var(--primary-text)' }}>
              Upload Screenshots
            </h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--secondary-text)', marginTop: '4px' }}>
              PNG, JPG, WEBP or BMP · Max 50 MB each
            </p>
          </div>
          {state === "idle" && (
            <button onClick={onClose} style={{ color: '#9CA3AF', transition: 'color 0.15s', cursor: 'pointer', background: 'none', border: 'none', padding: '4px' }}>
              <X size={22} />
            </button>
          )}
        </div>

        {/* Body */}
        <div style={{ padding: '24px 28px 28px' }}>
          {state === "idle" && (
            <>
              {/* Drop Zone */}
              <div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onClick={() => inputRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? 'var(--accent)' : '#E5E5E5'}`,
                  borderRadius: '12px',
                  padding: '40px 20px',
                  textAlign: 'center',
                  background: dragOver ? 'rgba(29,78,216,0.04)' : '#FAFAFA',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  marginBottom: files.length ? '16px' : '0'
                }}
              >
                <div style={{ width: '52px', height: '52px', background: '#EFF6FF', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', color: 'var(--accent)' }}>
                  <Upload size={24} />
                </div>
                <p style={{ fontWeight: 600, color: 'var(--primary-text)', marginBottom: '6px' }}>
                  Drop files here or click to browse
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--secondary-text)' }}>
                  Supports PNG, JPG, WEBP, BMP
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept={ALLOWED.join(",")}
                  multiple
                  onChange={e => addFiles(e.target.files)}
                  style={{ display: 'none' }}
                />
              </div>

              {/* Error */}
              {errorMsg && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#DC2626', fontSize: '0.85rem', marginTop: '12px' }}>
                  <AlertCircle size={16} />
                  {errorMsg}
                </div>
              )}

              {/* File list */}
              {files.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
                  {files.map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 12px', background: '#F9FAFB', borderRadius: '8px', border: '1px solid #E5E5E5' }}>
                      <FileImage size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
                      <span style={{ flex: 1, fontSize: '0.85rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--secondary-text)' }}>{(f.size / 1024 / 1024).toFixed(1)} MB</span>
                      <button onClick={() => removeFile(i)} style={{ color: '#9CA3AF', background: 'none', border: 'none', cursor: 'pointer' }}>
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
                <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>Cancel</button>
                <button
                  className="btn btn-primary"
                  style={{ flex: 2, justifyContent: 'center' }}
                  disabled={files.length === 0}
                  onClick={handleUpload}
                >
                  <Upload size={15} />
                  Upload {files.length > 0 ? `${files.length} file${files.length > 1 ? 's' : ''}` : ''}
                </button>
              </div>
            </>
          )}

          {(state === "uploading" || state === "polling") && (
            <div style={{ padding: '16px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px', color: 'var(--accent)' }}>
                <Loader size={20} style={{ animation: 'spin 1s linear infinite' }} />
                <span style={{ fontWeight: 600 }}>
                  {state === "uploading" ? "Uploading files…" : "AI processing in background…"}
                </span>
              </div>

              {progress.map((p, i) => (
                <div key={i} style={{ padding: '12px 14px', background: '#F9FAFB', borderRadius: '8px', border: '1px solid #E5E5E5', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <FileImage size={16} color="var(--accent)" />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: '0.85rem', marginBottom: '3px' }}>{p.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--secondary-text)' }}>{p.status}</div>
                  </div>
                </div>
              ))}

              {state === "polling" && (
                <p style={{ fontSize: '0.8rem', color: 'var(--secondary-text)', marginTop: '12px', textAlign: 'center' }}>
                  OCR + AI extraction is running in the background. This may take 5–20 seconds per file.
                </p>
              )}
            </div>
          )}

          {state === "done" && (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div style={{ width: '56px', height: '56px', background: '#F0FDF4', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', color: '#16a34a' }}>
                <CheckCircle size={28} />
              </div>
              <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px' }}>
                All done!
              </h3>
              <p style={{ color: 'var(--secondary-text)', fontSize: '0.875rem' }}>
                Your screenshots have been processed. Returning to dashboard…
              </p>
            </div>
          )}

          {state === "error" && (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{ width: '52px', height: '52px', background: '#FEF2F2', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', color: '#DC2626' }}>
                <AlertCircle size={26} />
              </div>
              <p style={{ color: '#DC2626', fontWeight: 600, marginBottom: '8px' }}>Upload failed</p>
              <p style={{ color: 'var(--secondary-text)', fontSize: '0.85rem', marginBottom: '16px' }}>{errorMsg}</p>
              <button className="btn btn-secondary" onClick={() => setState("idle")}>Try again</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
