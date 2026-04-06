import { useState, useRef } from 'react'
import { basename } from '../../lib/pathUtils'

const COLL_STYLES = {
  docs:     'text-teal',
  codebase: 'text-accent',
  legacy:   'text-amber',
}

export function SearchPanel() {
  const [query,   setQuery]   = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [coll,    setColl]    = useState('')
  const [expanded,setExpanded]= useState(null)
  const debounce  = useRef(null)

  const search = async (q, c) => {
    if (!q.trim()) { setResults([]); return }
    setLoading(true)
    try {
      const r = await fetch('/api/rag/search', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ query: q, top_k: 12, collection: c || undefined }),
      })
      const d = await r.json()
      setResults(d.results ?? [])
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const onChange = (q) => {
    setQuery(q)
    clearTimeout(debounce.current)
    debounce.current = setTimeout(() => search(q, coll), 500)
  }

  const scoreColor = (s) =>
    s > 0.88 ? 'text-teal' : s > 0.75 ? 'text-accent' : 'text-muted'

  return (
    <div className="space-y-3">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            value={query}
            onChange={e => onChange(e.target.value)}
            placeholder="semantic search the index…"
            className="w-full bg-surface border border-border rounded-lg
                       pl-4 pr-10 py-2 text-sm font-mono text-gray-200
                       placeholder:text-muted
                       focus:outline-none focus:border-accent/60 transition-colors"
          />
          {loading && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2
                             w-3 h-3 border border-accent border-t-transparent
                             rounded-full animate-spin" />
          )}
        </div>
        <select
          value={coll}
          onChange={e => { setColl(e.target.value); search(query, e.target.value) }}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-xs
                     font-mono text-gray-300 focus:outline-none focus:border-accent/60"
        >
          <option value="">all collections</option>
          <option value="docs">docs</option>
          <option value="codebase">codebase</option>
          <option value="legacy">legacy</option>
        </select>
      </div>

      {/* Results */}
      {results.length === 0 && query && !loading && (
        <p className="text-xs text-muted py-2">
          No results — is Ollama running with <span className="font-mono">nomic-embed-text</span>?
        </p>
      )}

      <div className="space-y-1.5">
        {results.map((r, i) => {
          const isOpen = expanded === i
          const cc = COLL_STYLES[r.collection] ?? 'text-muted'
          return (
            <div
              key={i}
              className="border border-border rounded-lg overflow-hidden
                         hover:border-border/80 transition-colors"
            >
              {/* Row */}
              <button
                onClick={() => setExpanded(isOpen ? null : i)}
                className="w-full flex items-center gap-3 px-3 py-2.5 text-left"
              >
                <span className={`font-mono text-sm font-semibold w-12 flex-shrink-0 ${scoreColor(r.score)}`}>
                  {r.score.toFixed(3)}
                </span>
                <span className="font-mono text-xs text-gray-200 flex-1 truncate">
                  {basename(r.source_path)}
                  <span className="text-muted">:{r.chunk_index}</span>
                </span>
                <span className={`font-mono text-[10px] flex-shrink-0 ${cc}`}>
                  {r.collection}
                </span>
                <span className="font-mono text-[10px] text-muted flex-shrink-0">
                  {r.language}
                </span>
                <ChevronIcon open={isOpen} />
              </button>

              {/* Expanded text */}
              {isOpen && (
                <div className="border-t border-border bg-surface px-3 py-2.5">
                  <p className="text-[11px] text-muted font-mono mb-1 truncate">
                    {r.source_path}
                  </p>
                  <pre className="text-[11px] font-mono text-gray-400 whitespace-pre-wrap
                                  max-h-40 overflow-y-auto leading-relaxed">
                    {r.text}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ChevronIcon({ open }) {
  return (
    <svg className={`w-3 h-3 text-muted flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
         viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
