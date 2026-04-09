import { useState, useEffect, useCallback, useRef } from 'react'
import { FileExplorer } from './FileExplorer'
import { FileViewer } from './FileViewer'
import { AgentPanel } from './AgentPanel'
import { ActivityPanel } from './ActivityPanel'
import { useWebSocket } from '../../hooks/useWebSocket'
import { api } from '../../lib/api'

export function WorkspaceLayout() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [showFileViewer, setShowFileViewer] = useState(true)
  const [activityMinimized, setActivityMinimized] = useState(true)

  const [channels, setChannels] = useState([])
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState({})
  const [activeAgent, setActiveAgent] = useState(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [sending, setSending] = useState(false)
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState([])

  const handleWsEvent = useCallback((ev) => {
    const { event, payload } = ev
    if (event === '_connected') { setConnected(true); return }
    if (event === '_disconnected') { setConnected(false); return }

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
      if (!activeAgent) setActiveAgent(m.agent_id)
      const id = payload.id || payload.message_id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.question, time: new Date().toISOString() }, ...prev].slice(0, 100))
      return
    }

    if (event === 'reply_confirmed') {
      const { id, message_id, reply, replied_at } = payload
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
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: `${payload.agent_id} is ${payload.status}`, time: new Date().toISOString() }, ...prev].slice(0, 100))
      return
    }

    if (event === 'log') {
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.message?.slice(0, 120) || 'Log entry', time: new Date().toISOString() }, ...prev].slice(0, 100))
      return
    }

    if (event.includes('task') || event.includes('phase') || event.includes('iter') || event.includes('build')) {
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.text || payload.content || event, time: new Date().toISOString() }, ...prev].slice(0, 100))
    }
  }, [activeAgent])

  useWebSocket(handleWsEvent)

  const loadStatus = useCallback(async () => {
    try {
      const [channelsData, pending] = await Promise.all([
        api.channels().catch(() => []),
        api.pending().catch(() => ({ messages: [] }))
      ])
      setChannels(channelsData)
      setPendingCount(pending.messages?.length || 0)
      setMessages(prev => {
        const next = { ...prev }
        for (const m of (pending.messages ?? [])) {
          const arr = next[m.agent_id] ?? []
          const exists = arr.some(x => x.id === m.id)
          if (!exists) {
            next[m.agent_id] = [...arr, m]
          } else {
            next[m.agent_id] = arr.map(x => x.id === m.id ? m : x)
          }
        }
        return next
      })
      if (!activeAgent && channelsData.length > 0) {
        setActiveAgent(channelsData[0].agent_id)
      }
    } catch (error) {
      console.error('Failed to load status', error)
    }
  }, [activeAgent])

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 30000)
    return () => clearInterval(interval)
  }, [loadStatus])

  useEffect(() => {
    if (!activeAgent) return
    api.messages(activeAgent).then(msgs => {
      setMessages(prev => {
        const existing = prev[activeAgent] ?? []
        const existingIds = new Set(existing.map(m => m.id))
        const newMsgs = msgs.filter(m => !existingIds.has(m.id))
        return { ...prev, [activeAgent]: [...newMsgs, ...existing] }
      })
    }).catch(() => {})
  }, [activeAgent])

  const handleReply = async (msgId, text) => {
    if (sending) return
    setSending(true)
    try {
      const result = await api.reply(msgId, text)
      if (result?.message) {
        const confirmedMsg = result.message
        setPendingCount(n => Math.max(0, n - 1))
        setMessages(prev => {
          const list = prev[confirmedMsg.agent_id] ?? []
          const idx = list.findIndex(x => x.id === confirmedMsg.id)
          if (idx >= 0) {
            const updated = [...list]
            updated[idx] = confirmedMsg
            return { ...prev, [confirmedMsg.agent_id]: updated }
          }
          return { ...prev, [confirmedMsg.agent_id]: [confirmedMsg, ...list] }
        })
      }
    } catch (e) {
      console.error('reply failed', e)
    } finally {
      setSending(false)
    }
  }

  const handleFileSelect = (file) => {
    setSelectedFile(file)
    setShowFileViewer(true)
  }

  const handleCloseFile = () => {
    setSelectedFile(null)
    setShowFileViewer(false)
  }

  return (
    <div className="h-screen flex flex-col bg-slate-950 overflow-hidden">
      <Header
        connected={connected}
        pendingCount={pendingCount}
        agentCount={channels?.length || 0}
        onLogoClick={() => {}}
      />

      <div className="flex-1 flex overflow-hidden pb-20">
        <div className="w-72 flex-shrink-0 border-r border-slate-800 overflow-hidden">
          <FileExplorer onFileSelect={handleFileSelect} />
        </div>

        <div className="flex-1 min-w-0 overflow-hidden">
          {showFileViewer && selectedFile ? (
            <FileViewer file={selectedFile} onClose={handleCloseFile} />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 bg-slate-950 p-8">
              <WelcomeIcon className="w-20 h-20 mb-6 text-slate-700" />
              <h2 className="text-xl font-semibold text-slate-400 mb-3">AgentCraft Workspace</h2>
              <p className="text-sm text-slate-500 text-center max-w-lg mb-8">
                Browse project files, communicate with agents, and monitor activity in real-time.
              </p>
              <div className="flex items-center gap-6 text-xs text-slate-600">
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-violet-500" />
                  <span>Documentation</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-amber-500" />
                  <span>Workflow</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-teal-500" />
                  <span>Generated Project</span>
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="w-80 flex-shrink-0 overflow-hidden border-l border-slate-800">
          <AgentPanel
            channels={channels}
            statuses={statuses}
            messages={messages}
            activeAgent={activeAgent}
            setActiveAgent={setActiveAgent}
            sending={sending}
            onReply={handleReply}
          />
        </div>
      </div>

      <ActivityPanel 
        events={events} 
        onMinimize={setActivityMinimized}
      />
    </div>
  )
}

function Header({ connected, pendingCount, agentCount, onLogoClick }) {
  return (
    <header className="h-12 flex-shrink-0 bg-slate-900 border-b border-slate-800 flex items-center px-4 gap-3">
      <button onClick={onLogoClick} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
        <div className="w-6 h-6 rounded-md bg-accent/20 border border-accent/30 flex items-center justify-center">
          <TerminalIcon />
        </div>
        <span className="font-semibold text-sm text-slate-200">AgentCraft</span>
      </button>

      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-teal' : 'bg-danger'}`} />
        <span className="text-[11px] text-slate-500">{connected ? 'connected' : 'reconnecting…'}</span>
      </div>

      <div className="flex-1" />

      {pendingCount > 0 && (
        <div className="flex items-center gap-1.5 bg-amber/10 border border-amber/30 rounded-full px-3 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
          <span className="text-xs text-amber font-medium">
            {pendingCount} waiting {pendingCount === 1 ? 'reply' : 'replies'}
          </span>
        </div>
      )}

      <a href="/classic" className="text-xs text-slate-500 hover:text-slate-300 px-2 py-1 rounded hover:bg-slate-800">
        Classic UI
      </a>
    </header>
  )
}

function WelcomeIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
      <line x1="9" y1="14" x2="15" y2="14" />
    </svg>
  )
}

function TerminalIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-accent" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
