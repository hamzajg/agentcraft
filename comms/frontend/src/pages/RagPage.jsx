import { useState, useEffect, useCallback } from 'react'

const POLL_MS = 8000

export function RagPage() {
  const [stats,      setStats]      = useState(null)
  const [files,      setFiles]      = useState([])
  const [queries,    setQueries]    = useState(null)
  const [search,     setSearch]     = useState({ q: '', results: [], loading: false })
  const [activeTab,  setActiveTab]  = useState('overview')
  const [reindexing, setReindexing] = useState(false)
  const [error,      setError]      = useState(null)

  const load = useCallback(async () => {
    try {
      const [s, f, q] = await Promise.all([
        fetch('/api/rag/stats').then(r => r.json()),
        fetch('/api/rag/files?limit=200').then(r => r.json()),
        fetch('/api/rag/queries?limit=30').then(r => r.json()),
      ])
      setStats(s); setFiles(Array.isArray(f) ? f : []); setQueries(q)
      setError(null)
    } catch { setError('Cannot reach RAG API') }
  }, [])

  useEffect(() => { load(); const t = setInterval(load, POLL_MS); return () => clearInterval(t) }, [load])

  const doSearch = async () => {
    if (!search.q.trim()) return
    setSearch(s => ({ ...s, loading: true, results: [] }))
    const r = await fetch('/api/rag/search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: search.q, top_k: 5 }),
    }).then(r => r.json()).catch(() => ({ results: [] }))
    setSearch(s => ({ ...s, loading: false, results: r.results ?? [] }))
  }

  const doReindex = async (force = false) => {
    setReindexing(true)
    await fetch('/api/rag/reindex', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force }),
    }).catch(() => {})
    setTimeout(() => { setReindexing(false); load() }, 3000)
  }

  const idx = stats?.index ?? {}
  const qs  = queries?.summary ?? {}

  const TABS = [
    { id: 'overview',  label: 'Overview'  },
    { id: 'files',     label: `Files (${files.length})` },
    { id: 'queries',   label: `Queries (${qs.total_queries ?? 0})` },
    { id: 'search',    label: 'Search'    },
  ]

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 animate-fade-in">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-200">RAG Repository</h2>
          <p className="text-xs text-muted mt-0.5">
            {error ? <span className="text-amber">{error}</span>
              : idx.status === 'ok'
                ? <span className="text-teal">● {idx.total_chunks?.toLocaleString()} chunks · {idx.total_files?.toLocaleString()} files</span>
                : <span className="text-muted">Store empty or unavailable</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <Btn onClick={() => doReindex(false)} disabled={reindexing}>
            {reindexing ? '↻ indexing…' : '↻ re-index'}
          </Btn>
          <Btn onClick={() => doReindex(true)} disabled={reindexing}>force</Btn>
        </div>
      </div>

      {/* Sub-nav */}
      <div className="flex gap-1 bg-surface border border-border rounded-lg p-0.5 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all
              ${activeTab === t.id ? 'bg-panel text-gray-200' : 'text-muted hover:text-gray-400'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Overview ── */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Card label="Chunks"     value={idx.total_chunks?.toLocaleString() ?? '—'} color="teal" />
            <Card label="Files"      value={idx.total_files?.toLocaleString()  ?? '—'} color="teal" />
            <Card label="Lines"      value={idx.total_lines?.toLocaleString()  ?? '—'} color="purple" />
            <Card label="Store"      value={`${stats?.store_size_mb ?? 0} MB`}          color="purple" />
          </div>
          {qs.total_queries > 0 && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <Card label="Queries"   value={qs.total_queries?.toLocaleString()} color="amber" />
              <Card label="Hit rate"  value={`${qs.hit_rate_pct}%`}              color="amber" />
              <Card label="Avg chunks" value={qs.avg_chunks}                     color="gray" />
              <Card label="Avg ms"    value={`${qs.avg_duration_ms}ms`}          color="gray" />
            </div>
          )}
          {idx.collections && <BarSection title="Collections" data={idx.collections} total={idx.total_chunks} color="teal" />}
          {idx.languages   && <BarSection title="Languages"   data={idx.languages}   total={idx.total_chunks} color="purple" />}
          {queries?.top_sources?.length > 0 && (
            <Panel title="Most retrieved files">
              {queries.top_sources.slice(0, 8).map((s, i) => (
                <div key={i} className="flex items-center gap-3 py-1">
                  <span className="text-[10px] text-muted w-4">{i + 1}</span>
                  <span className="font-mono text-[11px] text-gray-300 flex-1 truncate">
                    {s.source?.split('/').slice(-2).join('/')}
                  </span>
                  <span className="text-xs text-amber shrink-0">{s.hits} hits</span>
                </div>
              ))}
            </Panel>
          )}
        </div>
      )}

      {/* ── Files ── */}
      {activeTab === 'files' && (
        <Panel title={`${files.length} indexed files`}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="text-muted border-b border-border text-left">
                  {['File', 'Collection', 'Language', 'Chunks', 'Lines', 'Chars'].map(h => (
                    <th key={h} className={`py-2 pr-4 font-medium ${['Chunks','Lines','Chars'].includes(h) ? 'text-right' : ''}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {files.map((f, i) => (
                  <tr key={i} className="border-b border-border/40 hover:bg-white/5 transition-colors">
                    <td className="py-1.5 pr-4 max-w-xs">
                      <div className="flex items-center gap-1">
                        {!f.exists && <span className="text-danger text-[9px]">✗</span>}
                        <span className="font-mono text-[11px] text-gray-300 truncate" title={f.path}>
                          {f.path?.split('/').slice(-3).join('/')}
                        </span>
                      </div>
                    </td>
                    <td className="py-1.5 pr-4"><CollBadge col={f.collection} /></td>
                    <td className="py-1.5 pr-4 font-mono text-[10px] text-muted">{f.language}</td>
                    <td className="py-1.5 pr-4 text-right font-mono text-[11px] text-teal">{f.chunks}</td>
                    <td className="py-1.5 pr-4 text-right font-mono text-[11px] text-gray-400">{f.lines?.toLocaleString()}</td>
                    <td className="py-1.5 text-right font-mono text-[11px] text-muted">{f.chars?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* ── Queries ── */}
      {activeTab === 'queries' && queries && (
        <div className="space-y-4">
          {queries.by_agent?.length > 0 && (
            <Panel title="Per agent">
              {queries.by_agent.map((a, i) => (
                <div key={i} className="flex items-center gap-4 text-xs py-1">
                  <span className="font-mono text-teal w-24 truncate">{a.agent_id || '—'}</span>
                  <span className="text-gray-300">{a.queries} queries</span>
                  <span className="text-muted">avg {Number(a.avg_chunks).toFixed(1)} chunks</span>
                  <span className="text-muted">{Number(a.avg_ms).toFixed(0)} ms avg</span>
                </div>
              ))}
            </Panel>
          )}
          <Panel title="Recent queries">
            <div className="font-mono text-[11px] space-y-0.5">
              {queries.recent?.map((q, i) => {
                const ts  = new Date(q.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                const hit = q.chunks_returned > 0
                return (
                  <div key={i} className="grid grid-cols-[60px_80px_24px_1fr] gap-2 py-0.5 border-b border-border/40 items-center">
                    <span className="text-muted text-[10px]">{ts}</span>
                    <span className={`truncate ${hit ? 'text-teal' : 'text-danger'}`}>{q.agent_id || '—'}</span>
                    <span className={`text-right ${hit ? 'text-teal' : 'text-danger'}`}>{q.chunks_returned}</span>
                    <span className="text-gray-300 truncate" title={q.query_text}>{q.query_text}</span>
                  </div>
                )
              })}
            </div>
          </Panel>
        </div>
      )}

      {/* ── Search ── */}
      {activeTab === 'search' && (
        <Panel title="Semantic search test">
          <div className="flex gap-2">
            <input
              value={search.q}
              onChange={e => setSearch(s => ({ ...s, q: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && doSearch()}
              placeholder="e.g. AgentMessage sealed class reactive Mono"
              className="flex-1 bg-surface border border-border rounded-lg px-4 py-2.5
                         text-sm text-gray-200 placeholder:text-muted font-mono
                         focus:outline-none focus:border-accent/60 transition-colors"
            />
            <button onClick={doSearch} disabled={search.loading || !search.q.trim()}
              className="px-5 rounded-lg bg-accent text-white text-sm font-medium
                         disabled:opacity-40 hover:bg-accent/90 transition-colors">
              {search.loading ? '…' : 'Search'}
            </button>
          </div>
          {search.results.length > 0 && (
            <div className="space-y-3 mt-3">
              {search.results.map((r, i) => (
                <div key={i} className="bg-surface border border-border rounded-lg p-3 space-y-2">
                  <p className="font-mono text-[10px] text-accent truncate">{r.source}</p>
                  <pre className="text-[11px] text-gray-400 whitespace-pre-wrap leading-relaxed max-h-28 overflow-y-auto">
                    {r.preview}
                  </pre>
                </div>
              ))}
            </div>
          )}
          {search.results.length === 0 && search.q && !search.loading && (
            <p className="text-sm text-muted mt-3">No results — try a different query or check the index.</p>
          )}
        </Panel>
      )}
    </div>
  )
}

// ── Atoms ──────────────────────────────────────────────────────────────────────

function Btn({ children, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="text-xs px-3 py-1.5 rounded-lg border border-border
                 text-muted hover:text-gray-200 hover:border-gray-500
                 disabled:opacity-40 transition-colors">
      {children}
    </button>
  )
}

function Card({ label, value, color }) {
  const tc = { teal:'text-teal', purple:'text-accent', amber:'text-amber', gray:'text-gray-400' }[color] ?? 'text-gray-200'
  return (
    <div className="bg-panel border border-border rounded-xl p-4">
      <p className="text-[10px] font-mono text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-xl font-semibold font-mono ${tc}`}>{value ?? '—'}</p>
    </div>
  )
}

function Panel({ title, children }) {
  return (
    <div className="bg-panel border border-border rounded-xl p-4 space-y-3">
      <p className="text-xs font-mono text-muted uppercase tracking-wider">{title}</p>
      {children}
    </div>
  )
}

function BarSection({ title, data, total, color }) {
  const tc  = color === 'teal' ? 'bg-teal' : 'bg-accent'
  return (
    <Panel title={title}>
      <div className="space-y-2">
        {Object.entries(data).sort((a,b) => b[1]-a[1]).map(([k, v]) => {
          const pct = total ? v / total * 100 : 0
          return (
            <div key={k} className="flex items-center gap-3">
              <span className="font-mono text-xs text-gray-400 w-20 truncate">{k}</span>
              <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
                <div className={`h-full ${tc} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
              </div>
              <span className="text-[11px] text-muted w-28 text-right font-mono">
                {v.toLocaleString()} <span className="text-muted/60">({pct.toFixed(1)}%)</span>
              </span>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

function CollBadge({ col }) {
  const map = { docs:'bg-teal/10 text-teal border-teal/30', codebase:'bg-accent/10 text-accent border-accent/30', legacy:'bg-amber/10 text-amber border-amber/30' }
  return <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${map[col] ?? 'border-border text-muted'}`}>{col}</span>
}
