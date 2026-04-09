import { useState, useRef, useEffect } from 'react'
import { Badge } from './ui'

const EVENT_ICONS = {
  build_started: '▶', build_done: '✓', build_error: '✕',
  phase_started: '◆', phase_done: '◆', iter_started: '→', iter_done: '←',
  task_started: '▶', task_done: '✓', aider_token: '…',
  file_written: '✎', reviewer_verdict: '⚖', approval_gate: '⏳',
  paused: '⏸', resumed: '▶', stopped: '⏹', error: '!',
  agent_query: '❓', agent_reply: '↩', agent_context: '≡',
  agent_delegate: '⇢', agent_broadcast: '◎', agent_status: '●',
  log: '…', clarification: '?', directive_injected: '⇢',
}

const EVENT_COLORS = {
  build_started: 'text-teal', build_done: 'text-teal', build_error: 'text-danger',
  task_started: 'text-accent', task_done: 'text-teal', error: 'text-danger',
  agent_query: 'text-amber', agent_reply: 'text-teal', agent_status: 'text-slate-400',
  agent_delegate: 'text-violet', agent_broadcast: 'text-cyan', agent_context: 'text-blue',
  clarification: 'text-amber', approval_gate: 'text-amber', reviewer_verdict: 'text-amber',
  paused: 'text-slate-400', resumed: 'text-teal', stopped: 'text-danger',
  file_written: 'text-teal', directive_injected: 'text-violet',
}

export function ActivityPanel({ events = [], onMinimize }) {
  const [isExpanded, setIsExpanded] = useState(false) // Start minimized
  const [isCollapsed, setIsCollapsed] = useState(false)
  const eventsEndRef = useRef(null)

  useEffect(() => {
    if (!isCollapsed && isExpanded) {
      eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, isCollapsed, isExpanded])

  const handleExpand = () => {
    setIsExpanded(true)
    setIsCollapsed(false)
  }

  const handleMinimize = () => {
    setIsExpanded(false)
  }

  // Only show button when minimized
  if (!isExpanded) {
    return (
      <button
        onClick={handleExpand}
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-full shadow-lg hover:bg-slate-700 transition-colors"
      >
        <svg className="w-4 h-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span className="text-sm text-slate-300">Activity</span>
        {events.length > 0 && (
          <span className="w-5 h-5 rounded-full bg-accent text-white text-xs font-bold flex items-center justify-center">
            {events.length > 99 ? '99+' : events.length}
          </span>
        )}
        <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 15l-6-6-6 6" />
        </svg>
      </button>
    )
  }

  // Expanded panel
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-slate-900 border-t border-slate-700 shadow-2xl">
      <div 
        className="flex items-center justify-between px-4 py-2 bg-slate-800/80 backdrop-blur-sm cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-3">
          <svg className="w-4 h-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <span className="text-sm font-medium text-slate-200">Activity</span>
          {events.length > 0 && (
            <Badge variant="muted" className="text-xs">{events.length} events</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleMinimize()
            }}
            className="p-1 rounded hover:bg-slate-700 transition-colors"
            title="Minimize"
          >
            <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
            </svg>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              setIsCollapsed(!isCollapsed)
            }}
            className="p-1 rounded hover:bg-slate-700 transition-colors"
            title={isCollapsed ? 'Expand' : 'Collapse'}
          >
            <svg className={`w-4 h-4 text-slate-400 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="h-48 overflow-y-auto">
          {events.length === 0 ? (
            <div className="flex items-center justify-center h-full text-slate-500">
              <p className="text-sm">No events yet. Events will appear here as agents work.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/50">
              {[...events].reverse().map((event, idx) => {
                const icon = EVENT_ICONS[event.type] || '●'
                const color = EVENT_COLORS[event.type] || 'text-slate-400'
                const time = event.time ? new Date(event.time).toLocaleTimeString([], { 
                  hour: '2-digit', 
                  minute: '2-digit',
                  second: '2-digit'
                }) : ''

                return (
                  <div 
                    key={event.id || idx} 
                    className="flex items-start gap-3 px-4 py-2 hover:bg-slate-800/30 transition-colors"
                  >
                    <span className={`${color} mt-0.5 flex-shrink-0 ${
                      event.type?.includes('started') || event.type?.includes('clarification') ? 'animate-pulse' : ''
                    }`}>
                      {icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-300 leading-relaxed line-clamp-2">
                        {event.text || event.content || event.message || event.type}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        {event.agent_id && (
                          <span className="text-xs text-slate-500 font-mono">{event.agent_id}</span>
                        )}
                        {time && (
                          <span className="text-xs text-slate-600">{time}</span>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
              <div ref={eventsEndRef} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
