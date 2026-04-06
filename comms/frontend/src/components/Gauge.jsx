export function Gauge({ label, pct, detail, color = 'teal' }) {
  const colorMap = {
    teal:   { bar: 'bg-teal',   text: 'text-teal',   dim: 'bg-teal/20'   },
    purple: { bar: 'bg-accent', text: 'text-accent',  dim: 'bg-accent/20' },
    amber:  { bar: 'bg-amber',  text: 'text-amber',   dim: 'bg-amber/20'  },
    red:    { bar: 'bg-red-500',text: 'text-red-400', dim: 'bg-red-500/20'},
  }
  const c      = colorMap[pct > 85 ? 'red' : pct > 65 ? 'amber' : color] ?? colorMap.teal
  const filled = Math.max(0, Math.min(100, pct))

  return (
    <div className="bg-panel border border-border rounded-xl p-4 flex flex-col gap-2.5">
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-mono text-muted uppercase tracking-wider">{label}</span>
        <span className={`text-2xl font-semibold font-mono ${c.text}`}>
          {pct.toFixed(1)}<span className="text-sm text-muted">%</span>
        </span>
      </div>

      {/* Bar */}
      <div className="h-1.5 bg-surface rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${c.bar}`}
          style={{ width: `${filled}%` }}
        />
      </div>

      {detail && (
        <p className="text-[11px] text-muted font-mono">{detail}</p>
      )}
    </div>
  )
}
