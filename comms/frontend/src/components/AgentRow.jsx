export function AgentRow({ channel, statuses, pendingAgents }) {
  const status  = statuses?.[channel.agent_id] ?? 'idle'
  const blocked = pendingAgents?.includes(channel.agent_id)
  const display = blocked ? 'blocked' : status

  const dot = {
    blocked:  'bg-amber animate-pulse',
    running:  'bg-teal animate-pulse',
    idle:     'bg-muted',
    complete: 'bg-teal',
  }[display] ?? 'bg-muted'

  const labelColor = {
    blocked: 'text-amber',
    running: 'text-teal',
    idle:    'text-muted',
    complete:'text-teal',
  }[display] ?? 'text-muted'

  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-white/5 transition-colors">
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
      <span className="font-mono text-xs text-gray-300 w-32 truncate">
        {channel.agent_label ?? channel.agent_id}
      </span>
      <span className={`font-mono text-xs ${labelColor} w-16`}>{display}</span>
      {channel.unread > 0 && (
        <span className="text-[10px] bg-amber/20 text-amber border border-amber/30
                         rounded-full px-2 py-0.5 font-medium">
          {channel.unread} waiting
        </span>
      )}
    </div>
  )
}
