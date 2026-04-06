export function StatCard({ label, value, sub, color = 'teal' }) {
  const c = {
    teal:   'text-teal   border-teal/20   bg-teal/5',
    purple: 'text-accent border-accent/20 bg-accent/5',
    amber:  'text-amber  border-amber/20  bg-amber/5',
    gray:   'text-muted  border-border    bg-panel',
  }[color] ?? 'text-teal border-teal/20 bg-teal/5'

  return (
    <div className={`rounded-xl border px-4 py-3 flex flex-col gap-1 ${c}`}>
      <span className="text-[10px] font-mono uppercase tracking-wider opacity-70">{label}</span>
      <span className="text-2xl font-semibold font-mono">{value}</span>
      {sub && <span className="text-[11px] opacity-60 font-mono">{sub}</span>}
    </div>
  )
}
