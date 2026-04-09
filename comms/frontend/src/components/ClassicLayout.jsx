import { useState, useEffect, useRef, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { api } from '../lib/api'
import { StatusDot } from '../v2/components/ui'

const TABS = [
  { id: 'live',    label: 'Live',    icon: LiveIcon },
  { id: 'chat',    label: 'Chat',    icon: ChatIcon },
  { id: 'monitor', label: 'Monitor', icon: MonitorIcon },
  { id: 'rag',     label: 'RAG',     icon: RagIcon },
  { id: 'bus',     label: 'Agent Bus', icon: BusIcon },
  { id: 'console', label: 'Console', icon: ConsoleIcon },
]

export function ClassicLayout() {
  const [tab,          setTab]          = useState('chat')
  const [connected,    setConnected]    = useState(false)
  const [channels,     setChannels]     = useState([])
  const [statuses,     setStatuses]     = useState({})
  const [messages,     setMessages]     = useState({})
  const [activeId,     setActiveId]     = useState(null)
  const [pendingCount, setPendingCount]  = useState(0)
  const [sending,      setSending]      = useState(false)
  const [logs,         setLogs]         = useState([])
  const bottomRef = useRef(null)

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
      document.title = `(${m.agent_label}) needs input — AgentCraft`
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
  }, [activeId])

  useWebSocket(handleWsEvent)

  useEffect(() => {
    if (!activeId) return
    if (messages[activeId]?.length > 0) return
    api.messages(activeId).then(msgs =>
      setMessages(prev => ({ ...prev, [activeId]: msgs }))
    ).catch(() => {})
  }, [activeId])
  
  useEffect(() => {
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

  const TabContent = () => {
    switch (tab) {
      case 'live': return <LivePage />
      case 'rag': return <RagPage />
      case 'bus': return <BusPage />
      case 'monitor': return <MonitorPage />
      case 'console': return <ConsolePage logs={logs} />
      default: return null
    }
  }

  return (
    <div className="h-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden">

      <header className="h-12 flex-shrink-0 bg-slate-900 border-b border-slate-800
                         flex items-center px-4 gap-3 select-none">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-accent/20 border border-accent/30
                          flex items-center justify-center">
            <TerminalIcon />
          </div>
          <span className="font-semibold text-sm tracking-tight">AgentCraft</span>
        </div>

        <div className="flex items-center gap-1.5 ml-1">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-teal' : 'bg-danger'}`} />
          <span className="text-[11px] text-slate-500">{connected ? 'connected' : 'reconnecting…'}</span>
        </div>

        <div className="flex items-center gap-1 ml-4 bg-slate-950 rounded-lg p-0.5 border border-slate-800">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`
                flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium
                transition-all
                ${tab === id
                  ? 'bg-slate-800 text-slate-200 shadow-sm'
                  : 'text-slate-500 hover:text-slate-400'}
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
            <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
            <span className="text-xs text-amber font-medium">
              {pendingCount} waiting {pendingCount === 1 ? 'reply' : 'replies'}
            </span>
          </div>
        )}
      </header>

      <div className="flex-1 flex overflow-hidden">
        {tab === 'chat' && (
          <Sidebar
            channels={channels}
            statuses={statuses}
            activeId={activeId}
            onSelect={selectChannel}
          />
        )}

        {tab === 'live' ? (
          <LivePage />
        ) : tab === 'rag' ? (
          <RagPage />
        ) : tab === 'bus' ? (
          <BusPage />
        ) : tab === 'monitor' ? (
          <MonitorPage />
        ) : tab === 'console' ? (
          <ConsolePage logs={logs} />
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            {activeId && (
              <div className="h-11 flex-shrink-0 border-b border-slate-800 bg-slate-900
                              flex items-center px-5 gap-3">
                <StatusDot status={statuses[activeId] ?? 'idle'} />
                <span className="font-mono text-sm font-medium text-slate-200">
                  {activeChannel?.agent_label ?? activeId}
                </span>
                <span className="text-[11px] text-slate-500 font-mono">{activeId}</span>
                {pendingMsg && (
                  <span className="ml-auto text-xs text-amber flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
                    Waiting for your reply
                  </span>
                )}
              </div>
            )}

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

function Sidebar({ channels, statuses, activeId, onSelect }) {
  return (
    <aside className="w-48 flex-shrink-0 border-r border-slate-800 bg-slate-950 overflow-y-auto">
      <div className="p-3 border-b border-slate-800">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2 px-3">Channels</p>
      </div>
      <div className="p-2 space-y-1">
        {channels.length === 0 ? (
          <p className="text-xs text-slate-600 px-3 py-2">No channels</p>
        ) : (
          channels.map((channel) => (
            <button
              key={channel.agent_id}
              onClick={() => onSelect(channel.agent_id)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors
                ${activeId === channel.agent_id 
                  ? 'bg-accent/10 text-accent' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
                }
              `}
            >
              <StatusDot status={statuses[channel.agent_id] || 'idle'} size="sm" />
              <span className="truncate flex-1">{channel.agent_label || channel.agent_id}</span>
              {(channel.unread > 0 || channel.total > 0) && (
                <span className="text-[10px] text-slate-500">{channel.total}</span>
              )}
            </button>
          ))
        )}
      </div>
    </aside>
  )
}

function AgentBubble({ msg, onSuggestionClick, onDismiss }) {
  const formatTime = (ts) => {
    if (!ts) return ''
    const d = new Date(ts)
    const now = new Date()
    const diff = (now - d) / 1000
    if (diff < 60) return 'Just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className={`rounded-xl border p-4 ${
      msg.status === 'pending' 
        ? 'border-amber/30 bg-amber/5' 
        : 'border-slate-800 bg-slate-900/50'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center text-xs font-medium text-accent">
            {msg.agent_id[0].toUpperCase()}
          </div>
          <span className="text-xs font-medium text-slate-300">@{msg.agent_id}</span>
        </div>
        <div className="flex items-center gap-2">
          {msg.status === 'pending' && (
            <span className="flex items-center gap-1 text-xs text-amber">
              <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
              Awaiting reply
            </span>
          )}
          <span className="text-[11px] text-slate-500">{formatTime(msg.created_at)}</span>
          {onDismiss && (
            <button onClick={() => onDismiss(msg.id)} className="text-slate-500 hover:text-slate-300">
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 4L4 12M4 4l8 8" strokeLinecap="round" />
              </svg>
            </button>
          )}
        </div>
      </div>
      
      <p className="text-sm text-slate-200 whitespace-pre-wrap">{msg.question}</p>

      {msg.suggestions?.length > 0 && msg.status === 'pending' && (
        <div className="border-t border-slate-700/50 pt-3 mt-3">
          <p className="text-xs text-slate-500 mb-2">Quick replies:</p>
          <div className="flex flex-wrap gap-2">
            {msg.suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => onSuggestionClick(s)}
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700 
                           text-slate-300 hover:bg-accent hover:border-accent/30 hover:text-white transition-colors"
              >
                {s.length > 40 ? s.slice(0, 40) + '...' : s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function YouBubble({ msg }) {
  const formatTime = (ts) => {
    if (!ts) return ''
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="rounded-xl border border-teal/30 bg-teal/5 p-4 ml-8">
      <div className="flex items-center gap-2 mb-1.5">
        <div className="w-4 h-4 rounded-full bg-teal/20 flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-teal" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 8a6 6 0 11-12 0 6 6 0 0112 0zM2 8h12" />
          </svg>
        </div>
        <span className="text-xs font-medium text-teal">You</span>
        <span className="text-xs text-slate-500 ml-auto">{formatTime(msg.replied_at)}</span>
      </div>
      <p className="text-sm text-slate-200 whitespace-pre-wrap">{msg.reply}</p>
    </div>
  )
}

function ReplyBar({ pendingMsgId, agentLabel, onSend, disabled }) {
  const [text, setText] = useState('')

  const handleSubmit = () => {
    if (!text.trim() || disabled) return
    onSend(text)
    setText('')
  }

  return (
    <div className="border-t border-slate-800 p-4 bg-slate-900">
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder={pendingMsgId ? `Reply to ${agentLabel}...` : 'Select a channel...'}
          disabled={!pendingMsgId || disabled}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm 
                     text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent/50
                     disabled:opacity-50"
        />
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || !pendingMsgId || disabled}
          className="px-4 py-2 rounded-lg bg-accent hover:bg-accent/90 disabled:opacity-40 
                     disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}

function NoChannel() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
      <svg className="w-16 h-16 mb-4 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
      <p className="text-sm">Select a channel to view messages</p>
    </div>
  )
}

function NoMessages({ agentLabel }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
      <svg className="w-16 h-16 mb-4 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" />
      </svg>
      <p className="text-sm">No messages with {agentLabel}</p>
    </div>
  )
}

import { LivePage } from '../pages/LivePage'
import { RagPage } from '../pages/RagPage'
import { BusPage } from '../pages/BusPage'
import { MonitorPage } from '../pages/MonitorPage'
import { ConsolePage } from '../pages/ConsolePage'

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

function LiveIcon() {
  return (
    <svg width='16' height='16' viewBox='0 0 16 16' fill='none'
         stroke='currentColor' strokeWidth='1.5' strokeLinecap='round'>
      <circle cx='8' cy='8' r='2'/>
      <path d='M8 1v2M8 13v2M1 8h2M13 8h2'/>
      <path d='M3.5 3.5l1.5 1.5M11 11l1.5 1.5M11 5L9.5 6.5M5 11l-1.5 1.5'/>
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
