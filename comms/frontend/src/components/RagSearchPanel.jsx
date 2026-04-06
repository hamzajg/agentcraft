import { useState } from 'react'

const COLL_COLOR = {
  docs:     'text-teal',
  codebase: 'text-accent',
  legacy:   'text-amber',
}

export function RagSearchPanel() {
  const [query,   setQuery]   = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [coll,    setColl]    = useState('')

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ q: query, top_k: 10 })
      if (coll) params.set('collection', coll)
      const r = await fetch(`/api/rag/search?${params}`)
      const d = await r.json()
      setResults(d.results ?? [])
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="flex gap-2">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder='Search the RAG index e.g. "supervisor actor message bus"'
          className="flex-1 bg-surface border border-border rounded-lg px-4 py-2.5
                     text-sm font-mono text-gray-200 placeholder:text-muted
                     focus:outline-none focus:border-accent/60"
        />
        <select
          value={coll}
          onChange={e => setColl(e.target.value)}
          className="bg-surface border border-border rounded-lg px-3 text-xs
                     text-muted font-mono focus:outline-none focus:border-accent/60"
        >
          <option value="">All collections</option>
          <option value="docs">docs</option>
          <option value="codebase">codebase</option>
          <option value="legacy">legacy</option>
        </select>
        <button
          onClick={search}
          disabled={loading || !query.trim()}
          className="px-4 py-2.5 bg-accent hover:bg-accent/90 text-white text-sm
                     font-medium rounded-lg disabled:opacity-40 transition-all
                     active:scale-95"
        >
          {loading ? '…' : 'Search'}
        </button>
      </div>

      {/* Results */}
      {results !== null && (
        results.length === 0 ? (
          <p className="text-sm text-muted text-center py-8">
            No results — try a different query or check RAG is enabled.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted">{results.length} results for "{query}"</p>
            {results.map((r, i) => {
              const name  = r.source_path.split('/').pop()
              const color = COLL_COLOR[r.collection] ?? 'text-gray-400'
              return (
                <div key={i}
                     className="bg-panel border border-border rounded-xl p-4 space-y-2
                                hover:border-border/80 transition-colors">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono font-medium text-muted">
                      #{i + 1}
                    </span>
                    <span className={`font-mono text-xs font-semibold ${color}`}>
                      {r.collection}
                    </span>
                    <span className="font-mono text-sm text-gray-200">{name}</span>
                    <span className="text-[10px] text-muted">chunk {r.chunk_index}</span>
                    <span className="text-[10px] text-muted ml-auto">
                      {r.language}
                    </span>
                  </div>
                  <pre className="text-[11px] font-mono text-gray-400 whitespace-pre-wrap
                                  bg-surface rounded-lg p-3 overflow-x-auto max-h-32
                                  border border-border leading-relaxed">
                    {r.text}
                  </pre>
                  <p className="text-[10px] text-muted font-mono truncate">
                    {r.source_path}
                  </p>
                </div>
              )
            })}
          </div>
        )
      )}
    </div>
  )
}
