/**
 * Horizontal proportion bar — used for collection and language breakdowns.
 * pct: 0–100
 */
export function RagBar({ label, pct, count, detail, color = 'teal' }) {
  const colorMap = {
    teal:   'bg-teal',
    purple: 'bg-accent',
    amber:  'bg-amber',
    gray:   'bg-muted',
  }
  const textMap = {
    teal:   'text-teal',
    purple: 'text-accent',
    amber:  'text-amber',
    gray:   'text-muted',
  }
  const bar = colorMap[color] ?? 'bg-teal'
  const txt = textMap[color] ?? 'text-teal'

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className={`font-mono font-medium ${txt}`}>{label}</span>
        <div className="flex items-center gap-3 text-muted">
          {detail && <span>{detail}</span>}
          <span className="text-gray-300 font-mono">{count?.toLocaleString()}</span>
          <span className="w-10 text-right">{pct.toFixed(1)}%</span>
        </div>
      </div>
      <div className="h-1.5 bg-surface rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${bar}`}
          style={{ width: `${Math.max(1, pct)}%` }}
        />
      </div>
    </div>
  )
}
