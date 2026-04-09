const statusColors = {
  running: 'bg-teal',
  idle: 'bg-slate-500',
  pending: 'bg-amber',
  blocked: 'bg-danger',
  stopped: 'bg-slate-700',
}

export function StatusDot({ status = 'idle', size = 'md', pulse = false }) {
  const sizes = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-3 h-3',
  }

  return (
    <span
      className={`
        inline-block rounded-full
        ${sizes[size]}
        ${statusColors[status] || statusColors.idle}
        ${pulse ? 'animate-pulse' : ''}
      `}
    />
  )
}

export function StatusBadge({ status }) {
  const variants = {
    running: 'success',
    idle: 'muted',
    pending: 'warning',
    blocked: 'danger',
    stopped: 'muted',
  }

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium
        ${variants[status] === 'success' ? 'bg-teal/20 text-teal' : ''}
        ${variants[status] === 'muted' ? 'bg-slate-800 text-slate-400' : ''}
        ${variants[status] === 'warning' ? 'bg-amber/20 text-amber' : ''}
        ${variants[status] === 'danger' ? 'bg-danger/20 text-danger' : ''}
      `}
    >
      <StatusDot status={status} size="sm" />
      {status}
    </span>
  )
}
