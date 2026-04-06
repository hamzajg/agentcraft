import { useState } from 'react'

const COLL_COLOR = {
  docs:     'text-teal   border-teal/30   bg-teal/10',
  codebase: 'text-accent border-accent/30 bg-accent/10',
  legacy:   'text-amber  border-amber/30  bg-amber/10',
}

export function RagFileTable({ files, onFileClick }) {
  const [sort, setSort]     = useState('chunks')  // 'chunks'|'lines'|'name'
  const [filter, setFilter] = useState('')

  const sorted = [...files]
    .filter(f => !filter ||
      f.source_path.toLowerCase().includes(filter.toLowerCase()) ||
      f.language.toLowerCase().includes(filter.toLowerCase())
    )
    .sort((a, b) => {
      if (sort === 'chunks') return b.chunk_count - a.chunk_count
      if (sort === 'lines')  return b.line_count  - a.line_count
      return a.source_path.localeCompare(b.source_path)
    })

  const maxChunks = files.length ? Math.max(...files.map(f => f.chunk_count)) : 1

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-3">
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter files…"
          className="flex-1 bg-surface border border-border rounded-lg px-3 py-1.5
                     text-xs font-mono text-gray-300 placeholder:text-muted
                     focus:outline-none focus:border-accent/60"
        />
        <div className="flex items-center gap-1 text-[10px] text-muted">
          Sort:
          {[['chunks','Chunks'],['lines','Lines'],['name','Name']].map(([v,l]) => (
            <button key={v} onClick={() => setSort(v)}
              className={`px-2 py-1 rounded ${sort === v
                ? 'bg-accent/20 text-accent' : 'hover:text-gray-300'}`}>
              {l}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-muted">{sorted.length} files</span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-panel">
              <th className="text-left px-4 py-2 text-muted font-medium">File</th>
              <th className="text-left px-3 py-2 text-muted font-medium">Collection</th>
              <th className="text-left px-3 py-2 text-muted font-medium">Language</th>
              <th className="text-right px-3 py-2 text-muted font-medium">Chunks</th>
              <th className="text-right px-4 py-2 text-muted font-medium">Lines</th>
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, 50).map((f, i) => {
              const name = f.source_path.split('/').pop()
              const dir  = f.source_path.split('/').slice(0, -1).join('/').slice(-30)
              const pct  = f.chunk_count / maxChunks * 100
              const cc   = COLL_COLOR[f.collection] ?? 'text-gray-400'

              return (
                <tr
                  key={f.source_path}
                  className={`border-b border-border/50 hover:bg-white/5 cursor-pointer
                              transition-colors ${i % 2 === 0 ? '' : 'bg-white/[0.02]'}`}
                  onClick={() => onFileClick?.(f.source_path)}
                >
                  <td className="px-4 py-2">
                    <div className="font-mono text-gray-200 truncate max-w-[260px]">{name}</div>
                    {dir && <div className="font-mono text-[10px] text-muted truncate">{dir}</div>}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${cc}`}>
                      {f.collection}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-muted">{f.language}</td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1 bg-surface rounded-full overflow-hidden">
                        <div className="h-full bg-accent/60 rounded-full"
                             style={{ width: `${pct}%` }} />
                      </div>
                      <span className="font-mono text-gray-300 w-8 text-right">
                        {f.chunk_count}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-muted">
                    {f.line_count?.toLocaleString()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {sorted.length > 50 && (
          <div className="px-4 py-2 text-center text-[10px] text-muted border-t border-border">
            Showing 50 of {sorted.length} files — use filter to narrow results
          </div>
        )}
      </div>
    </div>
  )
}
