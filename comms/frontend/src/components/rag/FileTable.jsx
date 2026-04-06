import { useState, useMemo } from 'react'
import { basename } from '../../lib/pathUtils'

const COLL_BADGE = {
  docs:     'bg-teal/15   text-teal   border-teal/30',
  codebase: 'bg-accent/15 text-accent  border-accent/30',
  legacy:   'bg-amber/15  text-amber   border-amber/30',
}

const LANG_BADGE = {
  java:       'text-amber',
  python:     'text-blue-300',
  markdown:   'text-teal',
  yaml:       'text-accent',
  json:       'text-yellow-300',
  shell:      'text-orange-300',
}

export function FileTable({ files }) {
  const [query,      setQuery]      = useState('')
  const [sortBy,     setSortBy]     = useState('chunks')   // chunks | name | lang
  const [filterColl, setFilterColl] = useState('all')
  const [filterLang, setFilterLang] = useState('all')

  const collections = useMemo(() =>
    ['all', ...new Set((files ?? []).map(f => f.collection))], [files])
  const languages   = useMemo(() =>
    ['all', ...new Set((files ?? []).map(f => f.language))], [files])

  const filtered = useMemo(() => {
    let f = files ?? []
    if (filterColl !== 'all') f = f.filter(x => x.collection === filterColl)
    if (filterLang !== 'all') f = f.filter(x => x.language   === filterLang)
    if (query) {
      const q = query.toLowerCase()
      f = f.filter(x => x.source_path.toLowerCase().includes(q))
    }
    return [...f].sort((a, b) =>
      sortBy === 'name'   ? basename(a.source_path).localeCompare(basename(b.source_path))
      : sortBy === 'lang' ? a.language.localeCompare(b.language)
      : b.chunk_count - a.chunk_count
    )
  }, [files, filterColl, filterLang, query, sortBy])

  if (!files?.length) return (
    <p className="text-xs text-muted py-4">No files indexed yet.</p>
  )

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap gap-2">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="filter by filename…"
          className="flex-1 min-w-40 bg-surface border border-border rounded-lg
                     px-3 py-1.5 text-xs font-mono text-gray-300 placeholder:text-muted
                     focus:outline-none focus:border-accent/60 transition-colors"
        />
        <Select value={filterColl} onChange={setFilterColl} options={collections} />
        <Select value={filterLang} onChange={setFilterLang} options={languages} />
        <Select value={sortBy} onChange={setSortBy}
          options={['chunks', 'name', 'lang']}
          label={v => `sort: ${v}`}
        />
      </div>

      {/* Count */}
      <p className="text-[10px] text-muted font-mono">
        {filtered.length.toLocaleString()} files
      </p>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left border-b border-border">
              <th className="pb-2 font-mono text-muted font-normal pr-4">File</th>
              <th className="pb-2 font-mono text-muted font-normal pr-4">Collection</th>
              <th className="pb-2 font-mono text-muted font-normal pr-4">Lang</th>
              <th className="pb-2 font-mono text-muted font-normal text-right pr-4">Chunks</th>
              <th className="pb-2 font-mono text-muted font-normal text-right">~Lines</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {filtered.slice(0, 100).map((f, i) => {
              const cb = COLL_BADGE[f.collection] ?? 'bg-muted/15 text-muted border-muted/30'
              const lc = LANG_BADGE[f.language] ?? 'text-muted'
              return (
                <tr key={i} className="hover:bg-white/3 transition-colors">
                  <td className="py-1.5 pr-4 font-mono text-gray-300 max-w-xs truncate"
                      title={f.source_path}>
                    {basename(f.source_path)}
                  </td>
                  <td className="py-1.5 pr-4">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] border ${cb}`}>
                      {f.collection}
                    </span>
                  </td>
                  <td className={`py-1.5 pr-4 font-mono ${lc}`}>{f.language}</td>
                  <td className="py-1.5 pr-4 text-right font-mono text-gray-300">
                    {f.chunk_count.toLocaleString()}
                  </td>
                  <td className="py-1.5 text-right font-mono text-muted">
                    {f.line_estimate.toLocaleString()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filtered.length > 100 && (
          <p className="text-[10px] text-muted mt-2 text-center">
            Showing 100 of {filtered.length.toLocaleString()} — use filter to narrow
          </p>
        )}
      </div>
    </div>
  )
}

function Select({ value, onChange, options, label }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="bg-surface border border-border rounded-lg px-2 py-1.5 text-xs
                 font-mono text-gray-300 focus:outline-none focus:border-accent/60
                 transition-colors cursor-pointer"
    >
      {options.map(o => (
        <option key={o} value={o}>{label ? label(o) : o}</option>
      ))}
    </select>
  )
}
