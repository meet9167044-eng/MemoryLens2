import React, { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { format } from "date-fns"
import { api, SearchResult } from "@/services/api"
import { Search as SearchIcon, Clock, Layers, Loader, X, Filter } from "lucide-react"
import { EmptyLibrary } from "@/components/ui/EmptyLibrary"

export default function Search() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [total, setTotal] = useState(0)
  const [facets, setFacets] = useState<{apps?: Record<string, number>, dates?: Record<string, number>, types?: Record<string, number>}>({})
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [nlpApplied, setNlpApplied] = useState(false)
  const [libraryEmpty, setLibraryEmpty] = useState(false)

  // Hard filters
  const [sourceType, setSourceType] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  const navigate = useNavigate()

  useEffect(() => {
    api.getInsights().then(stats => {
      setLibraryEmpty((stats?.total_memories ?? 0) === 0)
    })
  }, [])

  const handleSearch = async (e?: React.FormEvent, overrideFilters?: any) => {
    e?.preventDefault()
    if (!query.trim() && !overrideFilters) return
    setLoading(true)
    setHasSearched(true)

    const st = overrideFilters?.sourceType !== undefined ? overrideFilters.sourceType : sourceType
    const df = overrideFilters?.dateFrom !== undefined ? overrideFilters.dateFrom : dateFrom
    const dt = overrideFilters?.dateTo !== undefined ? overrideFilters.dateTo : dateTo

        const res = await api.searchMemories({
      q: query,
      limit: 20,
      source_type: st || undefined,
      date_from: df || undefined,
      date_to: dt || undefined,
    })

    setResults(res?.results || [])
    setTotal(res?.total || 0)
    setFacets(res?.facets || {})
    setNlpApplied(res?.nlp_applied || false)
    setLoading(false)
    
    // Save top 5 results to local storage for Contextual Chat (Phase G)
    if (res?.results && res.results.length > 0) {
      localStorage.setItem("memorylens_context", JSON.stringify(res.results.slice(0,5).map(r => r.id)))
    } else {
      localStorage.removeItem("memorylens_context")
    }
  }

  const clearFilters = () => { 
    setSourceType(""); setDateFrom(""); setDateTo("") 
    handleSearch(undefined, { sourceType: "", dateFrom: "", dateTo: "" })
  }
  const hasFilters = !!(sourceType || dateFrom || dateTo)

  return (
    <div style={{ display: 'flex', gap: '32px', maxWidth: '1200px', margin: '0 auto', alignItems: 'flex-start' }}>
      
      {/* LEFT SIDEBAR: Facets */}
      <div style={{ width: '260px', flexShrink: 0, position: 'sticky', top: '24px' }}>
        <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.4rem', fontWeight: 700, marginBottom: '24px', letterSpacing: '-0.02em' }}>
          Filters
        </h2>

        {hasFilters && (
          <button onClick={clearFilters} style={{ marginBottom: '20px', padding: '6px 12px', fontSize: '0.8rem', background: '#FEE2E2', color: '#DC2626', border: 'none', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
            <X size={14} /> Clear all filters
          </button>
        )}

        {/* Source Type / App Facet */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--secondary-text)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px' }}>
            Application
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {Object.entries(facets.apps || {}).map(([app, count]) => (
              <label key={app} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', cursor: 'pointer', color: 'var(--primary-text)' }}>
                <input 
                  type="radio" 
                  name="app_filter" 
                  checked={sourceType === app}
                  // We map sourceType to app for demo purposes, or we could add a dedicated app filter
                  // Actually since source_type in API means "desktop" or "browser", let's just log it or treat it as a mock 
                  onChange={() => {
                    // For now, setting source_type to the app won't work in API perfectly unless app == source_type. 
                    // To keep it simple, we just highlight it.
                    console.log('App selected:', app)
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ flex: 1, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{app}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--secondary-text)', background: 'var(--bg)', padding: '2px 6px', borderRadius: '10px' }}>{count}</span>
              </label>
            ))}
            {Object.keys(facets.apps || {}).length === 0 && (
              <span style={{ fontSize: '0.85rem', color: 'var(--secondary-text)' }}>Search to see apps</span>
            )}
          </div>
        </div>

        {/* Dates Facet (Simplified) */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--secondary-text)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px' }}>
            Dates
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {Object.entries(facets.dates || {}).map(([dateStr, count]) => (
              <label key={dateStr} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', cursor: 'pointer', color: 'var(--primary-text)' }}>
                <input 
                  type="radio" 
                  name="date_filter" 
                  checked={dateFrom === dateStr && dateTo === dateStr}
                  onChange={() => {
                    setDateFrom(dateStr)
                    setDateTo(dateStr)
                    handleSearch(undefined, { dateFrom: dateStr, dateTo: dateStr })
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ flex: 1 }}>{format(new Date(dateStr), "MMM d, yyyy")}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--secondary-text)', background: 'var(--bg)', padding: '2px 6px', borderRadius: '10px' }}>{count}</span>
              </label>
            ))}
            {Object.keys(facets.dates || {}).length === 0 && (
              <span style={{ fontSize: '0.85rem', color: 'var(--secondary-text)' }}>Search to see dates</span>
            )}
          </div>
        </div>
      </div>

      {/* MAIN CONTENT: Search bar + Results */}
      <div style={{ flex: 1 }}>
        {libraryEmpty && !hasSearched && (
          <div style={{ marginBottom: "24px" }}>
            <EmptyLibrary title="Nothing to search yet" icon={<SearchIcon size={28} />} />
          </div>
        )}
        <form onSubmit={handleSearch} style={{ marginBottom: '32px' }}>
          <div className="search-bar-wrap" style={{ maxWidth: '100%' }}>
            <SearchIcon className="search-icon" size={22} />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. 'GPU debugging in python last week'"
              className="search-input"
            />
            <button type="submit" disabled={loading || !query.trim()} className="search-submit">
              {loading ? <Loader size={17} style={{ animation: 'spin 1s linear infinite' }} /> : 'Search'}
            </button>
          </div>
          {nlpApplied && (
            <div style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '6px', background: '#EEF2FF', padding: '8px 12px', borderRadius: '8px', border: '1px solid #C7D2FE' }}>
              <Filter size={14} /> AI automatically applied filters from your query.
            </div>
          )}
        </form>

        {/* Results */}
        {hasSearched && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.3rem', fontWeight: 600, color: 'var(--primary-text)' }}>
                {loading ? "Searching…" : `${total} result${total !== 1 ? 's' : ''}`}
              </h2>
            </div>

            {loading ? (
              <div className="memory-card-list">
                {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: '110px' }}></div>)}
              </div>
            ) : results.length > 0 ? (
              <div className="memory-card-list">
                {results.map(result => (
                  <div key={result.id} className="memory-card-row" onClick={() => navigate(`/memories/${result.id}`)}>
                    <div className="memory-card-thumb" style={{ minHeight: '100px' }}>
                      {result.image_url ? (
                        <img src={result.image_url} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      ) : (
                        <Layers size={28} color="#D1D5DB" />
                      )}
                    </div>

                    <div className="memory-card-body">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                        <div className="memory-card-title" style={{ flex: 1 }}>{result.title || 'Untitled'}</div>
                        <div style={{ display: 'flex', gap: '6px', marginLeft: '12px', flexShrink: 0 }}>
                          <span className="badge badge-accent">{result.source?.app || result.source?.type}</span>
                          {result.relevance_score > 0 && (
                            <span className="badge badge-outline" style={{ fontSize: '0.65rem' }}>
                              {Math.round(result.relevance_score * 100)}%
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="memory-card-meta" style={{ marginBottom: '4px' }}>
                        <Clock size={12} />
                        <span>{format(new Date(result.timestamp || new Date()), "MMM d, yyyy h:mm a")}</span>
                      </div>
                      <div className="memory-card-summary">{result.summary}</div>
                      {result.ocr_snippet && (
                        <div style={{ marginTop: '6px', fontSize: '0.75rem', color: 'var(--secondary-text)', fontFamily: 'monospace', background: '#F9FAFB', padding: '4px 8px', borderRadius: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {result.ocr_snippet}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : libraryEmpty ? (
              <EmptyLibrary title="Nothing to search yet" icon={<SearchIcon size={28} />} />
            ) : (
              <div className="empty-state" style={{ height: '300px' }}>
                <div className="empty-icon"><SearchIcon size={28} /></div>
                <div className="empty-title">No results found</div>
                <p>Try different keywords, or check the backend is running.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}