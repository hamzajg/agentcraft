import { useState, useEffect, useCallback, useRef } from 'react'
import { Sidebar }        from './components/Sidebar'
import { AgentBubble, YouBubble } from './components/MessageBubble'
import { ReplyBar }       from './components/ReplyBar'
import { NoChannel, NoMessages } from './components/EmptyState'
import { StatusDot }      from './components/StatusDot'
import { MonitorPage }    from './pages/MonitorPage'
import { RagPage }        from './pages/RagPage'
import { BusPage }        from './pages/BusPage'
import { ConsolePage }    from './pages/ConsolePage'
import { useWebSocket }   from './hooks/useWebSocket'
import { api }            from './lib/api'

const TABS = [
  { id: 'chat',    label: 'Chat',    icon: ChatIcon    },
  { id: 'monitor', label: 'Monitor', icon: MonitorIcon },
  { id: 'rag',     label: 'RAG',     icon: RagIcon     },
  { id: 'bus',     label: 'Agent Bus', icon: BusIcon     },
  { id: 'console', label: 'Console', icon: ConsoleIcon },
]

export default function App() {
  const [tab,         setTab]         = useState('chat')
  const [connected,   setConnected]   = useState(false)
  const [channels,    setChannels]    = useState([])
  const [statuses,    setStatuses]    = useState({})
  const [messages,    setMessages]    = useState({})
  const [activeId,    setActiveId]    = useState(null)
  const [pendingCount,setPendingCount]= useState(0)
  const [sending,     setSending]     = useState(false)
  const [logs,        setLogs]        = useState([])
  const bottomRef = useRef(null)

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const handleWsEvent = useCallback((ev) => {
    const { event, payload } = ev
    if (event === '_connected')    { setConnected(true);  return }
    if (event === '_disconnected') { setConnected(false); return }

    if (event === 'init') {
      setChannels(payload.channels ?? [])
      const msgs = {}
      ;(payload.pending ?? []).forEach(m => {
        if (!msgs[m.agent_id]) msgs[m.agent_id] = []
        msgs[m.agent_id].push(m)
      })
      setMessages(msgs)
      setPendingCount((payload.pending ?? []).length)
      
      // Auto-select architect if it has pending messages
      const architectPending = (payload.pending ?? []).find(m => m.agent_id === 'architect')
      if (architectPending && !activeId) {
        setActiveId('architect')
      }
      return
    }

    if (event === 'clarification') {
      const m = payload
      setMessages(prev => {
        const arr = prev[m.agent_id] ?? []
        const idx = arr.findIndex(x => x.id === m.id)
        const next = idx >= 0
          ? [...arr.slice(0, idx), m, ...arr.slice(idx + 1)]
          : [...arr, m]
        return { ...prev, [m.agent_id]: next }
      })
      setChannels(prev => {
        const exists = prev.find(c => c.agent_id === m.agent_id)
        if (exists) return prev.map(c => c.agent_id === m.agent_id
          ? { ...c, unread: (c.unread ?? 0) + 1, last_active: m.created_at } : c)
        return [...prev, { agent_id: m.agent_id, agent_label: m.agent_label,
                           unread: 1, last_active: m.created_at }]
      })
      setPendingCount(n => n + 1)
      const prev = document.title
      document.title = `(${m.agent_label}) needs input — Agent Comms`
      setTimeout(() => { document.title = prev }, 6000)
      return
    }

    if (event === 'reply_confirmed') {
      const { id, message_id, reply, replied_at, status } = payload
      const mid = id || message_id
      setMessages(prev => {
        const next = { ...prev }
        for (const aid of Object.keys(next)) {
          next[aid] = next[aid].map(m => {
            if (m.id === mid) {
              return { ...m, status: 'replied', reply, replied_at }
            }
            return m
          })
        }
        return next
      })
      setPendingCount(n => Math.max(0, n - 1))
      return
    }

    if (event === 'agent_status') {
      setStatuses(prev => ({ ...prev, [payload.agent_id]: payload.status }))
    }

    if (event === 'log') {
      setLogs(prev => [...prev, payload])
    }
  }, [])

  useWebSocket(handleWsEvent)

  // ── Load initial data ───────────────────────────────────────────────────
  useEffect(() => {
    // Load channels and pending messages
    Promise.all([
      api.channels().catch(() => []),
      api.pending().catch(() => ({ messages: [] }))
    ]).then(([channels, pending]) => {
      setChannels(channels)
      const msgs = {}
      pending.messages.forEach(m => {
        if (!msgs[m.agent_id]) msgs[m.agent_id] = []
        msgs[m.agent_id].push(m)
      })
      setMessages(msgs)
      setPendingCount(pending.messages.length)
      
      // Auto-select architect if it has pending messages
      const architectPending = pending.messages.find(m => m.agent_id === 'architect')
      if (architectPending && !activeId) {
        setActiveId('architect')
      }
    })
  }, [])

  const selectChannel = (id) => {
    setActiveId(id)
    setChannels(prev => prev.map(c => c.agent_id === id ? { ...c, unread: 0 } : c))
    setTab('chat')
  }

  const loadAgentHistory = async (agentId) => {
    if (!agentId) return
    try {
      const msgs = await api.messages(agentId)
      setMessages(prev => ({ ...prev, [agentId]: msgs }))
    } catch (e) {
      console.error('failed to load agent history', e)
    }
  }

  useEffect(() => {
    if (!activeId) return
    if (!messages[activeId] || messages[activeId].length === 0) {
      loadAgentHistory(activeId)
    }
  }, [activeId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeId])

  // ── Reply ─────────────────────────────────────────────────────────────────
  const activeMsgs    = activeId ? (messages[activeId] ?? []) : []
  const pendingMsg    = activeMsgs.find(m => m.status === 'pending') ?? null
  const activeChannel = channels.find(c => c.agent_id === activeId)

  const handleSend = async (text) => {
    if (!pendingMsg || sending) return
    setSending(true)
    try { await api.reply(pendingMsg.id, text) }
    catch (e) { console.error('reply failed', e) }
    finally   { setSending(false) }
  }

  const handleDismiss = async (id) => {
    await api.dismiss(id).catch(() => {})
    setMessages(prev => ({
      ...prev,
      [activeId]: prev[activeId].filter(m => m.id !== id),
    }))
  }

  const sorted = [...activeMsgs].sort(
    (a, b) => new Date(a.created_at) - new Date(b.created_at)
  )

  return (
    <div className="h-screen flex flex-col bg-surface text-gray-100 overflow-hidden">

      {/* ── Header ── */}
      <header className="h-12 flex-shrink-0 bg-panel border-b border-border
                         flex items-center px-4 gap-3 select-none">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-accent/20 border border-accent/30
                          flex items-center justify-center">
            <TerminalIcon />
          </div>
          <span className="font-semibold text-sm tracking-tight">Agent Comms</span>
        </div>

        <div className="flex items-center gap-1.5 ml-1">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-teal' : 'bg-danger'}`} />
          <span className="text-[11px] text-muted">{connected ? 'connected' : 'reconnecting…'}</span>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 ml-4 bg-surface rounded-lg p-0.5 border border-border">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`
                flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium
                transition-all
                ${tab === id
                  ? 'bg-panel text-gray-200 shadow-sm'
                  : 'text-muted hover:text-gray-400'}
              `}
            >
              <Icon />
              {label}
              {id === 'chat' && pendingCount > 0 && (
                <span className="ml-0.5 w-4 h-4 rounded-full bg-amber text-black
                                 text-[9px] font-bold flex items-center justify-center">
                  {pendingCount > 9 ? '9+' : pendingCount}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {pendingCount > 0 && (
          <div className="flex items-center gap-1.5 bg-amber/10 border border-amber/30
                          rounded-full px-3 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse-slow" />
            <span className="text-xs text-amber font-medium">
              {pendingCount} waiting {pendingCount === 1 ? 'reply' : 'replies'}
            </span>
          </div>
        )}
      </header>

      {/* ── Body ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* Sidebar — only visible on Chat tab */}
        {tab === 'chat' && (
          <Sidebar
            channels={channels}
            statuses={statuses}
            activeId={activeId}
            onSelect={selectChannel}
          />
        )}

        {/* Main content */}
        {tab === 'rag' ? (
          <RagPage />
        ) : tab === 'bus' ? (
          <BusPage />
        ) : tab === 'monitor' ? (
          <MonitorPage />
        ) : tab === 'console' ? (
          <ConsolePage logs={logs} />
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Channel header */}
            {activeId && (
              <div className="h-11 flex-shrink-0 border-b border-border bg-panel
                              flex items-center px-5 gap-3">
                <StatusDot status={statuses[activeId] ?? 'idle'} />
                <span className="font-mono text-sm font-medium text-gray-200">
                  {activeChannel?.agent_label ?? activeId}
                </span>
                <span className="text-[11px] text-muted font-mono">{activeId}</span>
                {pendingMsg && (
                  <span className="ml-auto text-xs text-amber flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse-slow" />
                    Waiting for your reply
                  </span>
                )}
              </div>
            )}

            {/* Messages */}
            {!activeId ? (
              <NoChannel />
            ) : sorted.length === 0 ? (
              <NoMessages agentLabel={activeChannel?.agent_label ?? activeId} />
            ) : (
              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
                {sorted.map(msg => (
                  <div key={msg.id} className="space-y-2">
                    <AgentBubble
                      msg={msg}
                      onSuggestionClick={handleSend}
                      onDismiss={msg.status !== 'pending' ? handleDismiss : null}
                    />
                    {msg.reply && <YouBubble msg={msg} />}
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
            )}

            {/* Reply bar */}
            {activeId && (
              <ReplyBar
                pendingMsgId={pendingMsg?.id ?? null}
                agentLabel={activeChannel?.agent_label ?? activeId}
                onSend={handleSend}
                disabled={sending}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Icons ─────────────────────────────────────────────────────────────────────
function TerminalIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-accent" viewBox="0 0 16 16" fill="none"
         stroke="currentColor" strokeWidth="1.5">
      <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M14 10a2 2 0 01-2 2H5l-3 3V4a2 2 0 012-2h8a2 2 0 012 2v6z"
            strokeLinejoin="round" />
    </svg>
  )
}

function RagIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <ellipse cx="8" cy="4" rx="6" ry="2" />
      <path d="M2 4v4c0 1.1 2.7 2 6 2s6-.9 6-2V4" />
      <path d="M2 8v4c0 1.1 2.7 2 6 2s6-.9 6-2V8" />
    </svg>
  )
}

function MonitorIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1" y="2" width="14" height="10" rx="1.5" />
      <path d="M5 15h6M8 12v3" strokeLinecap="round" />
      <path d="M4 9l2-3 2 2 2-4 2 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function BusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
         stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="3" cy="5" r="1.5"/>
      <circle cx="13" cy="5" r="1.5"/>
      <circle cx="8" cy="13" r="1.5"/>
      <path d="M4.5 5h7M3 6.5l5 5M13 6.5l-5 5"/>
    </svg>
  )
}

function ConsoleIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 6l4 4-4 4M8 14h6" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="1" y="1" width="14" height="14" rx="1" strokeLinejoin="round" />
    </svg>
  )
}