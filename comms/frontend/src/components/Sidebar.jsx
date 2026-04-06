import { StatusDot } from './StatusDot'

export function Sidebar({ channels, statuses, activeId, onSelect }) {
  return (
    <aside className="w-56 flex-shrink-0 bg-panel border-r border-border flex flex-col">
      <div className="px-4 py-3 border-b border-border">
        <p className="text-[10px] font-semibold tracking-widest text-muted uppercase">Agents</p>
      </div>

      <nav className="flex-1 overflow-y-auto py-2 space-y-0.5 px-2">
        {channels.length === 0 && (
          <p className="px-2 py-6 text-xs text-muted text-center">
            No agents yet.<br />Start a build to see agents here.
          </p>
        )}
        {channels.map(ch => {
          const status  = statuses[ch.agent_id] ?? 'idle'
          const active  = ch.agent_id === activeId
          const unread  = ch.unread ?? 0
          return (
            <button
              key={ch.agent_id}
              onClick={() => onSelect(ch.agent_id)}
              className={`
                w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left
                transition-colors text-sm
                ${active
                  ? 'bg-accent-dim text-white'
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}
              `}
            >
              <StatusDot status={status} />
              <span className="flex-1 truncate font-mono text-xs">
                {ch.agent_label ?? ch.agent_id}
              </span>
              {unread > 0 && (
                <span className="flex-shrink-0 bg-amber text-black text-[10px] font-bold
                                 w-4 h-4 rounded-full flex items-center justify-center">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Status legend */}
      <div className="px-4 py-3 border-t border-border space-y-1">
        {[
          ['blocked', 'bg-amber',  'Blocked'],
          ['running', 'bg-teal',   'Running'],
          ['idle',    'bg-muted',  'Idle'],
        ].map(([, cls, label]) => (
          <div key={label} className="flex items-center gap-2 text-[10px] text-muted">
            <span className={`w-1.5 h-1.5 rounded-full ${cls}`} />
            {label}
          </div>
        ))}
      </div>
    </aside>
  )
}
