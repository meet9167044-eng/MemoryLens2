import { useEffect, useState, useRef, useCallback } from "react"
import { api, GraphNode, GraphEdge } from "@/services/api"
import { Network, BookOpen, FolderKanban, Clock, Maximize } from "lucide-react"
import { EmptyLibrary } from "@/components/ui/EmptyLibrary"
import ForceGraph2D from 'react-force-graph-2d'

type Story = {
  id: string
  title: string
  memory_ids: string[]
  start_time: string | null
  end_time: string | null
  tags: string[]
  memory_count: number
}

type Project = {
  name: string
  memory_ids: string[]
  memory_count: number
}

type ConnectionsData = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_memories?: number
  stories?: Story[]
  projects?: Project[]
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

export default function Connections() {
  const [connections, setConnections] = useState<ConnectionsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'graph' | 'stories' | 'projects'>('graph')
  const fgRef = useRef<any>(null)
  
  // Container ref for responsive sizing
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      const data = await api.getConnections()
      setConnections(data)
      setLoading(false)
    }
    fetchData()
  }, [])
  
  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver(entries => {
      if (entries.length > 0) {
        const { width, height } = entries[0].contentRect
        setDimensions({ width, height })
      }
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [activeTab, loading])

  const tabs = [
    { id: 'graph' as const, label: 'Knowledge Graph', icon: Network },
    { id: 'stories' as const, label: 'Stories', icon: BookOpen },
    { id: 'projects' as const, label: 'Projects', icon: FolderKanban },
  ]

  // Graph rendering
  const getNodeColor = useCallback((node: any) => {
    switch (node.type) {
      case 'memory': return '#4F46E5' // Indigo
      case 'entity': return '#10B981' // Emerald
      case 'project': return '#F43F5E' // Rose
      case 'story': return '#EAB308' // Yellow
      case 'domain': return '#06B6D4' // Cyan
      default: return '#6B7280'
    }
  }, [])
  
  const getNodeVal = useCallback((node: any) => {
    switch (node.type) {
      case 'memory': return 5
      case 'entity': return 3
      case 'project': return 8
      case 'story': return 6
      case 'domain': return 4
      default: return 3
    }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="page-header">
        <div>
          <h1 className="page-title letterpress">Memory Connections</h1>
          <p className="page-subtitle">Discover relationships, stories, and projects in your captured memories.</p>
        </div>
        {connections && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <span className="badge badge-outline">{connections.nodes?.length || 0} nodes</span>
            <span className="badge badge-outline">{connections.edges?.length || 0} edges</span>
            {(connections.stories?.length ?? 0) > 0 && (
              <span className="badge badge-outline">{connections.stories!.length} stories</span>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              id={`connections-tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '10px 18px',
                border: 'none',
                background: 'transparent',
                borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                color: isActive ? 'var(--accent)' : 'var(--secondary-text)',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.88rem',
                cursor: 'pointer',
                transition: 'all 0.2s',
                marginBottom: '-1px',
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {loading ? (
        <div className="card" style={{ flex: 1, minHeight: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
          <div style={{ width: '52px', height: '52px', border: '4px solid #DBEAFE', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
          <p style={{ color: 'var(--secondary-text)' }}>Building knowledge graph...</p>
        </div>
      ) : (

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {/* ── GRAPH TAB ── */}
          {activeTab === 'graph' && (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
              {connections && connections.nodes?.length > 0 ? (
                <>
                  <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'center', background: 'var(--bg)' }}>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--secondary-text)', fontWeight: 600 }}>Nodes:</span>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.75rem' }}><span style={{width: 10, height: 10, borderRadius: '50%', background: '#4F46E5'}}></span> Memory</div>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.75rem' }}><span style={{width: 10, height: 10, borderRadius: '50%', background: '#10B981'}}></span> Entity</div>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.75rem' }}><span style={{width: 10, height: 10, borderRadius: '50%', background: '#F43F5E'}}></span> Project</div>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.75rem' }}><span style={{width: 10, height: 10, borderRadius: '50%', background: '#EAB308'}}></span> Story</div>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.75rem' }}><span style={{width: 10, height: 10, borderRadius: '50%', background: '#06B6D4'}}></span> Domain</div>
                    </div>
                    <div style={{ flex: 1 }} />
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button onClick={() => fgRef.current?.zoomToFit(400, 50)} className="btn btn-outline" style={{ padding: '6px', minWidth: 0 }} title="Zoom to fit"><Maximize size={16} /></button>
                    </div>
                  </div>

                  <div ref={containerRef} style={{ flex: 1, width: '100%', minHeight: '500px', background: 'var(--bg-secondary)', cursor: 'grab' }}>
                    <ForceGraph2D
                      ref={fgRef}
                      width={dimensions.width}
                      height={dimensions.height}
                      graphData={{
                        nodes: connections.nodes,
                        links: connections.edges
                      }}
                      nodeLabel="label"
                      nodeColor={getNodeColor}
                      nodeVal={getNodeVal}
                      linkColor={(link: any) => {
                        const type = link.data?.relType || ''
                        if (type === 'has_entity') return '#9CA3AF40'
                        if (type === 'has_project') return '#F43F5E60'
                        if (type === 'has_story') return '#EAB30860'
                        if (type === 'semantic') return '#8B5CF660'
                        if (type === 'temporal') return '#F59E0B60'
                        return '#D1D5DB'
                      }}
                      linkWidth={(link: any) => link.data?.score ? Math.max(1, link.data.score * 3) : 1}
                      linkDirectionalParticles={2}
                      linkDirectionalParticleSpeed={(d: any) => d.data?.score ? d.data.score * 0.01 : 0.005}
                      d3VelocityDecay={0.3}
                      onEngineStop={() => fgRef.current?.zoomToFit(400, 50)}
                    />
                  </div>
                </>
              ) : (
                <div style={{ padding: '40px' }}>
                  <EmptyLibrary title="Upload to get started" icon={<Network size={28} />} />
                </div>
              )}
            </div>
          )}

          {/* ── STORIES TAB ── */}
          {activeTab === 'stories' && (
            <div style={{ flex: 1 }}>
              {(connections?.stories?.length ?? 0) > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {connections!.stories!.map(story => (
                    <div key={story.id} className="card" style={{ padding: '20px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                        <div>
                          <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 700, fontSize: '1.1rem', color: 'var(--primary-text)', marginBottom: '4px' }}>
                            {story.title}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--secondary-text)', fontSize: '0.78rem' }}>
                            <Clock size={12} />
                            {story.start_time ? formatTime(story.start_time) : 'Unknown time'}
                            {story.end_time && story.start_time !== story.end_time && (
                               <span>→ {formatTime(story.end_time)}</span>
                            )}
                          </div>
                        </div>
                        <span className="badge badge-outline">
                          {story.memory_count} {story.memory_count === 1 ? 'screenshot' : 'screenshots'}
                        </span>
                      </div>
                      {story.tags.length > 0 && (
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {story.tags.slice(0, 6).map(tag => (
                            <span key={tag} className="tag">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="card empty-state" style={{ minHeight: '300px' }}>
                  <div className="connection-icon" style={{ width: '60px', height: '60px' }}>
                    <BookOpen size={28} />
                  </div>
                  <div className="empty-title" style={{ marginTop: '16px' }}>No stories yet</div>
                  <p>Stories group your screenshots by session. Upload more memories with timestamps to see your work sessions come to life.</p>
                </div>
              )}
            </div>
          )}

          {/* ── PROJECTS TAB ── */}
          {activeTab === 'projects' && (
            <div style={{ flex: 1 }}>
              {(connections?.projects?.length ?? 0) > 0 ? (
                <div className="connections-grid">
                  {connections!.projects!.map(project => (
                    <div key={project.name} className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div className="connection-icon" style={{ marginBottom: '12px' }}>
                        <FolderKanban size={22} />
                      </div>
                      <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 700, fontSize: '1.05rem', color: 'var(--primary-text)', marginBottom: '6px', textAlign: 'center' }}>
                        {project.name}
                      </div>
                      <span className="badge badge-outline">
                        {project.memory_count} {project.memory_count === 1 ? 'memory' : 'memories'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="card empty-state" style={{ minHeight: '300px' }}>
                  <div className="connection-icon" style={{ width: '60px', height: '60px' }}>
                    <FolderKanban size={28} />
                  </div>
                  <div className="empty-title" style={{ marginTop: '16px' }}>No projects detected</div>
                  <p>Projects are auto-detected from your tags and domains. Try tagging screenshots with <code>project-myapp</code> to group them.</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
