import { useState, useEffect, useCallback, useRef } from 'react'

const POLL_MS = 2000

const TYPE_COLORS = {
  query:     'text-blue-400',
  reply:     'text-teal',
  context:   'text-amber',
  delegate:  'text-accent',
  broadcast: 'text-muted',
}
const TYPE_ICONS = {
  query:     '?',
  reply:     '↩',
  context:   '⬡',
  delegate:  '→',
  broadcast: '◉',
}
const TYPE_LABELS = {
  query:     'QUERY',
  reply:     'REPLY',
  context:   'CONTEXT',
  delegate:  'DELEGATE',
  broadcast: 'BCAST',
}

export function BusPage() {
  const [messages,  setMessages]  = useState([])
  const [context,   setContext]   = useState({})
  const [filter,    setFilter]    = useState('all')  // all | query | context | delegate
  const [search,    setSearch]    = useState('')
  const [activeTab, setActiveTab] = useState('messages')
  const [error,     setError]     = useState(null)
  const bottomRef = useRef(null)
  const prevCountRef = useRef(0)

  const load = useCallback(async () => {
    try {
      const [msgs, ctx] = await Promise.all([
        fetch('/api/bus/messages?limit=200').then(r => r.json()),
        fetch('/api/bus/context').then(r => r.json()),
      ])
      setMessages(Array.isArray(msgs) ? msgs : [])
      setContext(ctx || {})
      setError(null)
    } catch { setError('Bus API unreachable — is a build running?') }
  }, [])

  useEffect(() => { load(); const t = setInterval(load, POLL_MS); return () => clearInterval(t) }, [load])

  // Auto-scroll on new messages
  useEffect(() => {
    if (messages.length > prevCountRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    prevCountRef.current = messages.length
  }, [messages.length])

  // Listen for real-time WS bus events
  useEffect(() => {
    const ws = new WebSocket(`ws://${location.host}/ws`)
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data)
        if (['agent_query','agent_reply','agent_context','agent_delegate','agent_broadcast']
            .includes(ev.event)) {
          load()
        }
      } catch {}
    }
    return () => ws.close()
  }, [load])

  const filtered = messages.filter(m => {
    if (filter !== 'all' && m.type !== filter) return false
    if (search) {
      const q = search.toLowerCase()
      const content = JSON.stringify(m.content || '').toLowerCase()
      return content.includes(q) || (m.from_agent||'').includes(q) || (m.to_agent||'').includes(q)
    }
    return true
  })

  const contextEntries = Object.entries(context)

  return (
    <div className="flex-1 overflow-hidden flex flex-col animate-fade-in">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border flex items-center gap-3 flex-shrink-0">
        <div>
          <h2 className="font-semibold text-gray-200 text-sm">Agent Bus</h2>
          <p className="text-xs text-muted mt-0.5">
            {error
              ? <span className="text-amber">{error}</span>
              : <span className="text-teal">
                  ● {messages.length} messages · {contextEntries.length} context keys
                </span>
            }
          </p>
        </div>
        {/* Sub-tabs */}
        <div className="ml-auto flex gap-1 bg-surface border border-border rounded-lg p-0.5">
          {[['messages', `Feed (${messages.length})`], ['context', `Context (${contextEntries.length})`]].map(([id, label]) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all
                ${activeTab === id ? 'bg-panel text-gray-200' : 'text-muted hover:text-gray-400'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Messages tab */}
      {activeTab === 'messages' && (
        <>
          {/* Filters */}
          <div className="px-5 py-2 border-b border-border flex items-center gap-2 flex-shrink-0">
            <div className="flex gap-1">
              {['all','query','reply','context','delegate','broadcast'].map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wide transition-all
                    ${filter === f
                      ? 'bg-accent/20 text-accent border border-accent/40'
                      : 'text-muted hover:text-gray-400 border border-transparent'}`}>
                  {f}
                </button>
              ))}
            </div>
            <input
              value={search} onChange={e => setSearch(e.target.value)}
              placeholder="search messages…"
              className="ml-auto w-48 bg-surface border border-border rounded px-3 py-1
                         text-xs text-gray-200 placeholder:text-muted
                         focus:outline-none focus:border-accent/40 font-mono"
            />
          </div>

          {/* Feed */}
          <div className="flex-1 overflow-y-auto px-5 py-3 space-y-1 font-mono text-xs">
            {filtered.length === 0 && (
              <div className="text-muted text-center py-12">
                {messages.length === 0
                  ? 'No agent-to-agent messages yet — start a build to see activity'
                  : 'No messages match the current filter'}
              </div>
            )}
            {filtered.map((msg, i) => (
              <BusMessageRow key={msg.id || i} msg={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        </>
      )}

      {/* Context tab */}
      {activeTab === 'context' && (
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2">
          {contextEntries.length === 0 && (
            <div className="text-muted text-center py-12 text-xs">
              No context published yet — agents share context during a build
            </div>
          )}
          {contextEntries.map(([key, value]) => (
            <ContextCard key={key} contextKey={key} value={value} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function BusMessageRow({ msg }) {
  const [expanded, setExpanded] = useState(false)
  const typeColor = TYPE_COLORS[msg.type] || 'text-muted'
  const typeIcon  = TYPE_ICONS[msg.type]  || '·'
  const typeLabel = TYPE_LABELS[msg.type] || msg.type?.toUpperCase()

  const ts = msg.ts
    ? new Date(msg.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : ''

  const preview = (() => {
    const c = msg.content
    if (!c) return ''
    if (typeof c === 'string') return c.slice(0, 80)
    if (c.question) return c.question.slice(0, 80)
    if (c.key)      return `${c.key}`
    if (c.event)    return c.event
    if (c.task?.description) return c.task.description.slice(0, 80)
    return JSON.stringify(c).slice(0, 80)
  })()

  return (
    <div
      onClick={() => setExpanded(x => !x)}
      className="group border border-border/40 hover:border-border rounded-lg px-3 py-2
                 cursor-pointer transition-all hover:bg-white/5"
    >
      <div className="flex items-center gap-2">
        {/* Type badge */}
        <span className={`shrink-0 w-16 text-[10px] font-bold tracking-wider ${typeColor}`}>
          {typeIcon} {typeLabel}
        </span>

        {/* Route */}
        <span className="shrink-0 text-gray-400">
          <span className="text-teal">{msg.from_agent}</span>
          {msg.to_agent && <>
            <span className="text-muted mx-1">→</span>
            <span className="text-gray-300">{msg.to_agent}</span>
          </>}
          {!msg.to_agent && <span className="text-muted ml-1">→ all</span>}
        </span>

        {/* Preview */}
        <span className="flex-1 text-muted truncate">{preview}</span>

        {/* Timestamp */}
        <span className="shrink-0 text-muted text-[10px]">{ts}</span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-border/40">
          {msg.task_id && (
            <div className="text-[10px] text-muted mb-1">
              task: <span className="text-gray-400">{msg.task_id}</span>
              {msg.iteration_id != null && <> · iter: <span className="text-gray-400">{msg.iteration_id}</span></>}
            </div>
          )}
          <pre className="text-[11px] text-gray-300 whitespace-pre-wrap leading-relaxed
                          max-h-48 overflow-y-auto">
            {formatContent(msg.content)}
          </pre>
        </div>
      )}
    </div>
  )
}

function ContextCard({ contextKey, value }) {
  const [expanded, setExpanded] = useState(false)
  const [role, topic] = contextKey.includes('.') ? contextKey.split('.', 2) : ['', contextKey]

  return (
    <div
      onClick={() => setExpanded(x => !x)}
      className="border border-border rounded-xl p-3 cursor-pointer
                 hover:bg-white/5 transition-all"
    >
      <div className="flex items-center gap-3">
        <span className="font-mono text-[10px] text-amber shrink-0">{contextKey}</span>
        {role && (
          <span className="text-[10px] px-1.5 py-0.5 rounded border border-border text-muted">
            {role}
          </span>
        )}
        <span className="text-[11px] text-muted flex-1 truncate font-mono">
          {typeof value === 'string' ? value.slice(0, 60) : JSON.stringify(value).slice(0, 60)}
        </span>
        <span className="text-muted text-[10px]">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <pre className="mt-2 pt-2 border-t border-border/40 text-[11px] text-gray-300
                        whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto font-mono">
          {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  )
}

function formatContent(content) {
  if (!content) return ''
  if (typeof content === 'string') return content
  try { return JSON.stringify(content, null, 2) }
  catch { return String(content) }
}
