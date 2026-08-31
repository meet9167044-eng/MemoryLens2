import React, { useState, useRef, useEffect } from "react"
import { format } from "date-fns"
import { api, ChatCitation } from "@/services/api"
import { Send, Loader, Bot, User, ExternalLink, Zap, Brain } from "lucide-react"
import { useNavigate } from "react-router-dom"

interface Message {
  role: "user" | "assistant"
  text: string
  citations?: ChatCitation[]
  model?: string
  searched?: number
}

const SUGGESTIONS = [
  "What were the last things I was debugging?",
  "Show me anything related to Python or CUDA",
  "What tools did I use this week?",
  "Find memories about error messages",
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const sendMessage = async (text?: string) => {
    const query = (text || input).trim()
    if (!query || loading) return

    const userMsg: Message = { role: "user", text: query }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setLoading(true)

    const ctx = localStorage.getItem('memorylens_context')
    const contextIds = ctx ? JSON.parse(ctx) : undefined
    const res = await api.chat(query, contextIds)
    setLoading(false)

    if (res) {
      setMessages(prev => [...prev, {
        role: "assistant",
        text: res.answer,
        citations: res.citations,
        model: res.model_used,
        searched: res.memories_searched,
      }])
    } else {
      setMessages(prev => [...prev, {
        role: "assistant",
        text: "Sorry, I couldn't connect to the backend. Make sure the server is running on port 8000.",
      }])
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)', maxWidth: '860px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px', flexShrink: 0 }}>
        <h1 className="page-title letterpress" style={{ fontSize: '2.2rem', marginBottom: '6px' }}>
          MemoryLens AI
        </h1>
        <p className="page-subtitle">Ask questions about your captured memories. Powered by Gemini.</p>
      </div>

      {/* Chat Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        paddingBottom: '20px',
        scrollbarWidth: 'thin',
        scrollbarColor: '#E5E5E5 transparent'
      }}>
        {messages.length === 0 ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingTop: '40px' }}>
            <div style={{ width: '64px', height: '64px', background: 'linear-gradient(135deg, var(--accent) 0%, #6366f1 100%)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '20px', boxShadow: '0 8px 24px rgba(29,78,216,0.3)' }}>
              <Brain size={30} color="white" />
            </div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', fontWeight: 600, color: 'var(--primary-text)', marginBottom: '8px' }}>
              Ask about your memories
            </h2>
            <p style={{ color: 'var(--secondary-text)', fontSize: '0.95rem', marginBottom: '32px', textAlign: 'center', maxWidth: '400px' }}>
              I can recall anything from your captured screenshots using AI.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', maxWidth: '480px', width: '100%' }}>
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(s)}
                  style={{
                    background: '#fff',
                    border: '1px solid var(--border)',
                    borderRadius: '10px',
                    padding: '12px 14px',
                    textAlign: 'left',
                    fontSize: '0.8rem',
                    color: 'var(--primary-text)',
                    cursor: 'pointer',
                    lineHeight: 1.5,
                    transition: 'border-color 0.15s, box-shadow 0.15s'
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--accent)'
                    ;(e.currentTarget as HTMLButtonElement).style.boxShadow = '0 2px 8px rgba(29,78,216,0.1)'
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)'
                    ;(e.currentTarget as HTMLButtonElement).style.boxShadow = 'none'
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', gap: '14px', flexDirection: msg.role === "user" ? "row-reverse" : "row", alignItems: 'flex-start' }}>
              {/* Avatar */}
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: msg.role === "user" ? 'var(--primary-text)' : 'linear-gradient(135deg, var(--accent) 0%, #6366f1 100%)',
                boxShadow: msg.role === "assistant" ? '0 4px 12px rgba(29,78,216,0.25)' : 'none'
              }}>
                {msg.role === "user" ? <User size={18} color="white" /> : <Bot size={18} color="white" />}
              </div>

              {/* Bubble */}
              <div style={{ maxWidth: '75%', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: msg.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{
                  background: msg.role === "user" ? 'var(--primary-text)' : '#fff',
                  color: msg.role === "user" ? '#fff' : 'var(--primary-text)',
                  borderRadius: msg.role === "user" ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                  padding: '14px 18px',
                  fontSize: '0.9rem',
                  lineHeight: 1.65,
                  border: msg.role === "assistant" ? '1px solid var(--border)' : 'none',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                  whiteSpace: 'pre-wrap',
                }}>
                  {msg.text}
                </div>

                {/* Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div style={{ width: '100%' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--secondary-text)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Sources ({msg.citations.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {msg.citations.map((c, ci) => (
                        <div
                          key={ci}
                          onClick={() => navigate(`/memories/${c.memory_id}`)}
                          style={{
                            background: '#F9FAFB',
                            border: '1px solid #E5E5E5',
                            borderLeft: '3px solid var(--accent)',
                            borderRadius: '8px',
                            padding: '10px 12px',
                            cursor: 'pointer',
                            transition: 'background 0.15s',
                          }}
                          onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.background = '#EFF6FF'}
                          onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.background = '#F9FAFB'}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.8rem', color: 'var(--primary-text)' }}>{c.title}</span>
                            <ExternalLink size={12} color="var(--accent)" style={{ flexShrink: 0, marginLeft: '8px' }} />
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--secondary-text)', marginBottom: '4px' }}>
                            {format(new Date(c.timestamp || new Date()), "MMM d, yyyy h:mm a")}
                          </div>
                          <div style={{ fontSize: '0.78rem', color: '#555', lineHeight: 1.5 }}>{c.snippet}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Model indicator */}
                {msg.role === "assistant" && msg.model && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.7rem', color: '#9CA3AF' }}>
                    <Zap size={11} />
                    {msg.model} · {msg.searched} memories searched
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Loading bubble */}
        {loading && (
          <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, var(--accent) 0%, #6366f1 100%)' }}>
              <Bot size={18} color="white" />
            </div>
            <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: '18px 18px 18px 4px', padding: '14px 18px', display: 'flex', gap: '5px', alignItems: 'center' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#9CA3AF', animation: `bounce 1.4s ${i * 0.2}s infinite` }}></div>
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ flexShrink: 0, paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask anything about your memories… (Enter to send)"
            rows={1}
            style={{
              flex: 1,
              padding: '14px 16px',
              borderRadius: '12px',
              border: '1.5px solid var(--border)',
              outline: 'none',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.95rem',
              lineHeight: 1.5,
              resize: 'none',
              background: '#fff',
              maxHeight: '140px',
              overflowY: 'auto',
              transition: 'border-color 0.2s',
            }}
            onFocus={e => (e.target as HTMLTextAreaElement).style.borderColor = 'var(--accent)'}
            onBlur={e => (e.target as HTMLTextAreaElement).style.borderColor = 'var(--border)'}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: loading || !input.trim() ? '#E5E5E5' : 'var(--accent)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              transition: 'background 0.15s',
              border: 'none',
              flexShrink: 0
            }}
          >
            {loading ? <Loader size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={18} />}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-8px); }
        }
      `}</style>
    </div>
  )
}
