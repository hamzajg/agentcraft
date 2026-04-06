export function StatusDot({ status }) {
  const map = {
    blocked:  'bg-amber  animate-pulse-slow',
    running:  'bg-teal   animate-pulse-slow',
    idle:     'bg-muted',
    complete: 'bg-teal',
  }
  return (
    <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${map[status] ?? 'bg-muted'}`} />
  )
}
