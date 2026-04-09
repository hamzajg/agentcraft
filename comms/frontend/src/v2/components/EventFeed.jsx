import { Card, CardBody, CardHeader, Badge } from './ui'

const EVENT_ICONS = {
  build_started: '▶',
  build_done: '✓',
  build_error: '✕',
  phase_started: '◆',
  phase_done: '◆',
  iter_started: '→',
  iter_done: '←',
  task_started: '▶',
  task_done: '✓',
  aider_token: '…',
  file_written: '✎',
  reviewer_verdict: '⚖',
  approval_gate: '⏳',
  paused: '⏸',
  resumed: '▶',
  stopped: '⏹',
  error: '!',
  agent_query: '❓',
  agent_reply: '↩',
  agent_context: '≡',
  agent_delegate: '⇢',
  agent_broadcast: '◎',
  agent_status: '●',
  log: '…',
  clarification: '?',
  directive_injected: '⇢',
}

const EVENT_COLORS = {
  build_started: 'text-teal',
  build_done: 'text-teal',
  build_error: 'text-danger',
  task_started: 'text-accent',
  task_done: 'text-teal',
  error: 'text-danger',
  agent_query: 'text-amber',
  agent_reply: 'text-teal',
  agent_delegate: 'text-violet',
  agent_broadcast: 'text-cyan',
  agent_context: 'text-blue',
  agent_status: 'text-slate-400',
  clarification: 'text-amber',
  approval_gate: 'text-amber',
  reviewer_verdict: 'text-amber',
  paused: 'text-slate-400',
  resumed: 'text-teal',
  stopped: 'text-danger',
  file_written: 'text-teal',
  directive_injected: 'text-violet',
}

export function EventFeed({ events = [], maxHeight = '400px' }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-100">Event Stream</h3>
          <Badge variant="muted">{events.length} events</Badge>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        <div 
          className="overflow-y-auto px-5 py-3 space-y-1"
          style={{ maxHeight }}
        >
          {events.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-500">
              No events yet. Events will appear here as they occur.
            </div>
          ) : (
            events.map((event, idx) => (
              <EventItem key={event.id || idx} event={event} />
            ))
          )}
        </div>
      </CardBody>
    </Card>
  )
}

function EventItem({ event }) {
  const icon = EVENT_ICONS[event.type] || '●'
  const color = EVENT_COLORS[event.type] || 'text-slate-400'
  const time = formatTime(event.time)

  return (
    <div className="flex items-start gap-3 py-2 border-b border-slate-800/50 last:border-0 animate-fade-in">
      <span className={`text-sm ${color} w-5 flex-shrink-0 mt-0.5`}>
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-300 truncate">
          {event.text || event.content || event.message || formatEvent(event)}
        </p>
        {event.agent_id && (
          <span className="text-xs text-slate-500 font-mono">{event.agent_id}</span>
        )}
      </div>
      <span className="text-xs text-slate-600 flex-shrink-0">{time}</span>
    </div>
  )
}

function formatEvent(event) {
  if (event.event) return event.event
  if (event.type) return event.type
  return 'Unknown event'
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}
