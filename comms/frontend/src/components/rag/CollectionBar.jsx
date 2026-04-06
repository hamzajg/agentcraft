const COLL_STYLES = {
  docs:     { bar: 'bg-teal',   text: 'text-teal',   dot: 'bg-teal'   },
  codebase: { bar: 'bg-accent', text: 'text-accent',  dot: 'bg-accent' },
  legacy:   { bar: 'bg-amber',  text: 'text-amber',   dot: 'bg-amber'  },
}

const def_ = { bar: 'bg-muted', text: 'text-muted', dot: 'bg-muted' }

export function CollectionBreakdown({ collections }) {
  if (!collections?.length) return null
  const total = collections.reduce((s, c) => s + c.chunk_count, 0)

  return (
    <div className="space-y-3">
      {/* Stacked bar */}
      <div className="h-2 rounded-full overflow-hidden flex">
        {collections.map(c => {
          const s = COLL_STYLES[c.name] ?? def_
          return (
            <div
              key={c.name}
              className={`${s.bar} transition-all duration-700`}
              style={{ width: `${c.pct_of_total}%` }}
              title={`${c.name}: ${c.pct_of_total}%`}
            />
          )
        })}
      </div>

      {/* Rows */}
      <div className="space-y-2">
        {collections.map(c => {
          const s = COLL_STYLES[c.name] ?? def_
          return (
            <div key={c.name} className="flex items-center gap-3">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.dot}`} />
              <span className={`font-mono text-xs w-20 ${s.text}`}>{c.name}</span>
              <div className="flex-1 h-1 bg-surface rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${s.bar}`}
                  style={{ width: `${c.pct_of_total}%` }}
                />
              </div>
              <span className="font-mono text-[11px] text-muted w-12 text-right">
                {c.pct_of_total.toFixed(0)}%
              </span>
              <span className="font-mono text-[11px] text-gray-400 w-20 text-right">
                {c.chunk_count.toLocaleString()} chunks
              </span>
              <span className="font-mono text-[11px] text-muted w-16 text-right">
                {c.file_count.toLocaleString()} files
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function LanguageBreakdown({ langDist }) {
  if (!langDist) return null
  const entries = Object.entries(langDist).sort((a, b) => b[1] - a[1]).slice(0, 8)
  const total   = entries.reduce((s, [, v]) => s + v, 0)

  const LANG_COLORS = {
    java:       'bg-amber/80  text-amber',
    python:     'bg-blue-400/80 text-blue-300',
    markdown:   'bg-teal/80   text-teal',
    yaml:       'bg-accent/80 text-accent',
    json:       'bg-yellow-400/80 text-yellow-300',
    shell:      'bg-orange-400/80 text-orange-300',
    properties: 'bg-pink-400/80 text-pink-300',
  }

  return (
    <div className="space-y-1.5">
      {entries.map(([lang, count]) => {
        const pct   = count / total * 100
        const [bg, txt] = (LANG_COLORS[lang] ?? 'bg-muted text-muted').split('  ')
        return (
          <div key={lang} className="flex items-center gap-3">
            <span className={`font-mono text-[11px] w-16 ${txt ?? 'text-muted'}`}>{lang}</span>
            <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${bg}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="font-mono text-[10px] text-muted w-10 text-right">
              {count.toLocaleString()}
            </span>
          </div>
        )
      })}
    </div>
  )
}
