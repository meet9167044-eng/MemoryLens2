import { useEffect, useState } from "react"
import { api, GraphNode, GraphEdge } from "@/services/api"
import { Network, Link2, Monitor, Code, Tag, Cpu, BookOpen, FolderKanban, Clock, Globe } from "lucide-react"

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

function EntityIcon({ label }: { label: string }) {
  const lower = (label || '').toLowerCase()
  if (lower.includes('code') || lower.includes('python') || lower.includes('javascript'))
    return <Code size={20} />
  if (lower.includes('gpu') || lower.includes('cuda') || lower.includes('cpu') || lower.includes('ml'))
    return <Cpu size={20} />
  if (lower.includes('tag') || lower.includes('topic'))
    return <Tag size={20} />
  if (lower.includes('.com') || lower.includes('github') || lower.includes('web'))
    return <Globe size={20} />
  return <Network size={20} />
}

function RelTypeBadge({ type }: { type: string }) {
  const colours: Record<string, string> = {
    shared_entity: '#3B82F6',
    shared_tag:    '#10B981',
    semantic:      '#8B5CF6',
    temporal:      '#F59E0B',
    domain:        '#EC4899',
    has_entity:    '#6B7280',
  }
  const colour = colours[type] || '#6B7280'
  return (
    <span style={{
      fontSize: '0.68rem',
      fontWeight: 600,
      padding: '2px 8px',
      borderRadius: '999px',
      background: colour + '20',
      color: colour,
      whiteSpace: 'nowrap',
    }}>
      {type.replace('_', ' ')}
    </span>
  )
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

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      const data = await api.getConnections()
      setConnections(data)
      setLoading(false)
    }
    fetchData()
  }, [])

  const tabs = [
    { id: 'graph' as const, label: 'Knowledge Graph', icon: Network },
    { id: 'stories' as const, label: 'Stories', icon: BookOpen },
    { id: 'projects' as const, label: 'Projects', icon: FolderKanban },
  ]

  return (
    <div>
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
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
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
        <div className="card" style={{ minHeight: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
          <div style={{ width: '52px', height: '52px', border: '4px solid #DBEAFE', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
          <p style={{ color: 'var(--secondary-text)' }}>Building knowledge graph...</p>
        </div>
      ) : (

        <>
          {/* ── GRAPH TAB ── */}
          {activeTab === 'graph' && (
            <div className="card" style={{ minHeight: '520px', display: 'flex', flexDirection: 'column' }}>
              {connections && connections.nodes?.length > 0 ? (
                <>
                  <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    {[
                      { label: 'memories', count: connections.nodes.filter(n => n.type === 'memory').length },
                      { label: 'entities', count: connections.nodes.filter(n => n.type === 'entity').length },
                      { label: 'relationships', count: connections.edges.filter(e => e.data?.relType !== 'has_entity').length },
                    ].map(({ label, count }) => (
                      <div key={label} style={{ fontSize: '0.8rem', color: 'var(--secondary-text)' }}>
                        <span style={{ fontWeight: 700, color: 'var(--primary-text)', fontSize: '1.1rem' }}>{count}</span> {label}
                      </div>
                    ))}
                  </div>

                  {/* Relationship type legend */}
                  <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--secondary-text)', fontWeight: 600 }}>Relationship types:</span>
                    {['shared_entity', 'shared_tag', 'semantic', 'temporal', 'domain'].map(t => (
                      <RelTypeBadge key={t} type={t} />
                    ))}
                  </div>

                  <div className="connections-grid" style={{ padding: '20px' }}>
                    {connections.nodes
                      .filter(n => n.type === 'entity')
                      .map(node => {
                        const connectedEdges = connections.edges.filter(
                          e => e.source === node.id || e.target === node.id
                        )
                        const memoryCount = connectedEdges.length
                        if (memoryCount === 0) return null

                        return (
                          <div key={node.id} className="connection-node">
                            <div className="connection-icon">
                              <EntityIcon label={node.label} />
                            </div>
                            <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 700, fontSize: '1rem', color: 'var(--primary-text)', marginBottom: '6px' }}>
                              {node.label}
                            </div>
                            <span className="badge badge-outline">
                              {memoryCount} {memoryCount === 1 ? 'memory' : 'memories'}
                            </span>
                            <div style={{ width: '100%', marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              {connectedEdges.slice(0, 3).map((edge, i) => {
                                const targetId = edge.source === node.id ? edge.target : edge.source
                                const targetNode = connections.nodes.find(n => n.id === targetId)
                                if (!targetNode || targetNode.type === 'entity') return null
                                return (
                                  <div key={i} style={{ background: 'var(--bg)', borderRadius: '8px', padding: '8px 10px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem' }}>
                                    <Monitor size={12} color="#9CA3AF" style={{ flexShrink: 0 }} />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500, flex: 1 }}>
                                      {targetNode.label || 'Memory'}
                                    </span>
                                    {edge.data?.relType && <RelTypeBadge type={edge.data.relType} />}
                                  </div>
                                )
                              })}
                              {memoryCount > 3 && (
                                <div style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 600 }}>
                                  + {memoryCount - 3} more
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                  </div>
                </>
              ) : (
                <div className="empty-state" style={{ flex: 1 }}>
                  <div className="connection-icon" style={{ width: '60px', height: '60px' }}>
                    <Link2 size={28} />
                  </div>
                  <div className="empty-title" style={{ marginTop: '16px' }}>No connections yet</div>
                  <p>Capture more memories to discover the relationships between your topics and entities.</p>
                </div>
              )}
            </div>
          )}

          {/* ── STORIES TAB ── */}
          {activeTab === 'stories' && (
            <div>
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
            <div>
              {(connections?.projects?.length ?? 0) > 0 ? (
                <div className="connections-grid">
                  {connections!.projects!.map(project => (
                    <div key={project.name} className="connection-node">
                      <div className="connection-icon">
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
        </>
      )}
    </div>
  )
}
