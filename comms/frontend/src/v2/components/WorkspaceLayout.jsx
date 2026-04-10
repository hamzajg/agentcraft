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
  const [busMessages, setBusMessages] = useState([])

  // ── Build progress state ─────────────────────────────────────────────
  const [buildState, setBuildState] = useState({
    status: 'idle',        // idle | preparing | running | paused | stopped | done | error
    currentPhase: null,
    currentIteration: null,
    currentTask: null,
    phasesCompleted: [],
    totalPhases: 0,
    totalIterations: 0,
    approvedCount: 0,
    rejectedCount: 0,
    deliveredArtifacts: [],
    message: '',
  })

  const handleWsEvent = useCallback((ev) => {
    const { event, payload } = ev
    if (event === '_connected') { setConnected(true); return }
    if (event === '_disconnected') { setConnected(false); return }

    // ── Clarification messages (agent → human) ─────────────────────────
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
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.question, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    if (event === 'reply_confirmed') {
      const { id, message_id, reply, replied_at } = payload
      const mid = id || message_id
      setMessages(prev => {
        const next = { ...prev }
        for (const aid of Object.keys(next)) {
          next[aid] = next[aid].map(m => {
            if (m.id === mid) return { ...m, status: 'replied', reply, replied_at }
            return m
          })
        }
        return next
      })
      setPendingCount(n => Math.max(0, n - 1))
      return
    }

    // ── Agent status updates ───────────────────────────────────────────
    if (event === 'agent_status') {
      setStatuses(prev => ({ ...prev, [payload.agent_id]: payload.status }))
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: `${payload.agent_id} → ${payload.status}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // ── Log messages ───────────────────────────────────────────────────
    if (event === 'log') {
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.message?.slice(0, 120) || 'Log entry', time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // ── Agent-to-Agent bus messages ────────────────────────────────────
    if (event.startsWith('agent_')) {
      const id = payload.id || crypto.randomUUID()
      const fromAgent = payload.from_agent || payload.agent_id || ''
      const toAgent = payload.to_agent || ''
      let text = ''

      switch (event) {
        case 'agent_query':
          text = `${fromAgent} → ${toAgent}: ${payload.content?.question || 'question'}`.slice(0, 120)
          break
        case 'agent_reply':
          text = `${fromAgent} ← ${toAgent}: reply`
          break
        case 'agent_delegate':
          text = `${fromAgent} → ${toAgent}: ${payload.content?.task?.description || 'task'}`.slice(0, 120)
          break
        case 'agent_context':
          text = `${fromAgent} shared: ${payload.content?.key || 'context'}`
          break
        case 'agent_broadcast':
          text = `${fromAgent}: ${payload.content?.event || 'broadcast'}`
          break
        default:
          text = `${fromAgent}: ${event}`
      }

      // Store bus message for AgentPanel display
      setBusMessages(prev => [{
        id, type: event, from_agent: fromAgent, to_agent: toAgent,
        content: payload.content, text, time: new Date().toISOString(),
      }, ...prev].slice(0, 100))

      setEvents(prev => [{ id, type: event, agent_id: fromAgent, text, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // ── Build progress tracking ────────────────────────────────────────
    if (event === 'build_started') {
      setBuildState(prev => ({
        ...prev, status: 'running', message: 'Build started',
        phasesCompleted: [], approvedCount: 0, rejectedCount: 0, deliveredArtifacts: [],
      }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: 'Build started', time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'build_done') {
      setBuildState(prev => ({ ...prev, status: 'done', message: `Build complete — ${payload.approved || 0} iterations approved` }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: `Build complete — ${payload.approved || 0} iterations`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'error') {
      setBuildState(prev => ({ ...prev, status: 'error', message: payload.message || 'Error occurred' }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent, text: payload.message || event, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'stopped') {
      setBuildState(prev => ({ ...prev, status: 'stopped', message: 'Build stopped by user' }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: 'Build stopped', time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'paused') {
      setBuildState(prev => ({ ...prev, status: 'paused', message: 'Build paused' }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: 'Build paused', time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'resumed') {
      setBuildState(prev => ({ ...prev, status: 'running', message: 'Build resumed' }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: 'Build resumed', time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Phase tracking
    if (event === 'phase_started') {
      setBuildState(prev => ({ ...prev, currentPhase: payload.phase, message: `Phase ${payload.phase}: ${payload.name || ''}` }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent_id, text: `Phase ${payload.phase}: ${payload.name || 'started'}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'phase_done') {
      setBuildState(prev => ({
        ...prev,
        phasesCompleted: [...prev.phasesCompleted, payload.phase],
        message: `Phase ${payload.phase} complete`,
      }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: `Phase ${payload.phase} done — ${payload.sprints || payload.iterations || 0} iterations`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Iteration tracking
    if (event === 'iter_started') {
      setBuildState(prev => ({ ...prev, currentIteration: payload.id, message: `Iteration ${payload.id}: ${payload.name || ''}` }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent_id, text: `Iter ${payload.id}: ${payload.name || 'started'}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'iter_done') {
      setBuildState(prev => ({
        ...prev,
        currentIteration: null,
        approvedCount: payload.approved ? (prev.approvedCount + 1) : prev.approvedCount,
        rejectedCount: !payload.approved ? (prev.rejectedCount + 1) : prev.rejectedCount,
        message: `Iteration ${payload.id} ${payload.approved ? 'approved' : 'rejected'}`,
      }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: `Iter ${payload.id} — ${payload.approved ? '✓' : '✗'}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Task tracking
    if (event === 'task_started') {
      setBuildState(prev => ({ ...prev, currentTask: { id: payload.id, agent: payload.agent, file: payload.file } }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent, text: `[${payload.agent}] ${payload.file || payload.description?.slice(0, 60) || ''}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }
    if (event === 'task_done') {
      setBuildState(prev => ({ ...prev, currentTask: null }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent, text: `[${payload.agent}] ${payload.file} — ${payload.verdict} (${payload.attempts} attempt(s))`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // File written
    if (event === 'file_written') {
      setBuildState(prev => ({
        ...prev,
        deliveredArtifacts: [...prev.deliveredArtifacts, payload.path],
      }))
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent, text: `File: ${payload.path}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Reviewer verdict
    if (event === 'reviewer_verdict') {
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, agent_id: payload.agent, text: `Review: ${payload.verdict}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Approval gate
    if (event === 'approval_gate') {
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: `Awaiting approval — iteration ${payload.iteration}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Directive injected
    if (event === 'directive_injected') {
      setEvents(prev => [{ id: crypto.randomUUID(), type: event, text: `Directive injected — task ${payload.task_id}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Generic catch for any remaining build/phase/iter/task events
    if (event.includes('task') || event.includes('phase') || event.includes('iter') || event.includes('build')) {
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.text || payload.content || event, time: new Date().toISOString() }, ...prev].slice(0, 200))
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
            next[m.agent_id] = arr.map(x => {
              // Never downgrade replied status back to pending
              if (x.id === m.id && x.status === 'replied') {
                return x // Keep replied status
              }
              return x.id === m.id ? m : x
            })
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
        const merged = [...existing]
        for (const m of msgs) {
          const idx = merged.findIndex(x => x.id === m.id)
          if (idx < 0) {
            merged.push(m)
          } else if (m.status === 'replied' && merged[idx].status !== 'replied') {
            // Never overwrite replied status with pending
            merged[idx] = m
          } else if (m.status !== 'replied' && merged[idx].status === 'replied') {
            // Keep replied status
          } else {
            merged[idx] = m
          }
        }
        // Sort by created_at ascending
        merged.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        return { ...prev, [activeAgent]: merged }
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

  // Load full message history for a specific agent
  const loadAgentMessages = useCallback(async (agentId) => {
    try {
      const msgs = await api.messages(agentId, 100)
      console.log(`[chat] loaded ${msgs?.length || 0} messages for ${agentId}`)
      if (msgs && msgs.length > 0) {
        const pendingCount = msgs.filter(m => m.status === 'pending').length
        console.log(`[chat] ${pendingCount} pending messages for ${agentId}`)
        setMessages(prev => {
          const existing = prev[agentId] ?? []
          const merged = [...existing]
          for (const m of msgs) {
            const idx = merged.findIndex(x => x.id === m.id)
            if (idx < 0) {
              merged.push(m)
            } else {
              // Update if status changed (e.g., pending -> replied)
              if (m.status !== merged[idx].status) {
                merged[idx] = m
              }
            }
          }
          merged.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
          return { ...prev, [agentId]: merged }
        })
      }
    } catch (e) {
      console.error('Failed to load messages for', agentId, e)
    }
  }, [])

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
        statuses={statuses}
        buildState={buildState}
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
            events={events}
            busMessages={busMessages}
            activeAgent={activeAgent}
            setActiveAgent={setActiveAgent}
            sending={sending}
            onReply={handleReply}
            onLoadMessages={loadAgentMessages}
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

function Header({ connected, pendingCount, agentCount, statuses, buildState, onLogoClick }) {
  const activeAgents = Object.entries(statuses).filter(([, s]) => s === 'running').length
  const blockedAgents = Object.entries(statuses).filter(([, s]) => s === 'blocked').length
  const idleAgents = Object.entries(statuses).filter(([, s]) => s === 'idle').length

  return (
    <header className="h-12 flex-shrink-0 bg-slate-900 border-b border-slate-800 flex items-center px-4 gap-3">
      <button onClick={onLogoClick} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
        <div className="w-6 h-6 rounded-md bg-accent/20 border border-accent/30 flex items-center justify-center">
          <TerminalIcon />
        </div>
        <span className="font-semibold text-sm text-slate-200">AgentCraft</span>
      </button>

      {/* Connection status */}
      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-teal' : 'bg-danger'}`} />
        <span className="text-[11px] text-slate-500">{connected ? 'connected' : 'reconnecting…'}</span>
      </div>

      {/* Build progress bar */}
      {buildState.status !== 'idle' && (
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Build status badge */}
          <span className={`flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${
            buildState.status === 'running' ? 'bg-teal/10 text-teal' :
            buildState.status === 'done' ? 'bg-teal/10 text-teal' :
            buildState.status === 'paused' ? 'bg-slate-700 text-slate-400' :
            buildState.status === 'stopped' ? 'bg-danger/10 text-danger' :
            buildState.status === 'error' ? 'bg-danger/10 text-danger' :
            'bg-slate-800 text-slate-400'
          }`}>
            {buildState.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />}
            {buildState.status === 'running' ? 'Running' :
             buildState.status === 'done' ? 'Done' :
             buildState.status === 'paused' ? 'Paused' :
             buildState.status === 'stopped' ? 'Stopped' :
             buildState.status === 'error' ? 'Error' :
             buildState.status}
          </span>

          {/* Current phase/iteration */}
          {buildState.currentPhase && (
            <span className="text-xs text-slate-400 truncate">
              Phase {buildState.currentPhase}
              {buildState.currentIteration && ` → Iter ${buildState.currentIteration}`}
            </span>
          )}

          {/* Approved/Rejected counters */}
          {(buildState.approvedCount > 0 || buildState.rejectedCount > 0) && (
            <div className="flex items-center gap-2 flex-shrink-0">
              {buildState.approvedCount > 0 && (
                <span className="text-xs text-teal">✓ {buildState.approvedCount}</span>
              )}
              {buildState.rejectedCount > 0 && (
                <span className="text-xs text-amber">✗ {buildState.rejectedCount}</span>
              )}
            </div>
          )}

          {/* Current task */}
          {buildState.currentTask && (
            <span className="text-xs text-slate-500 truncate">
              [{buildState.currentTask.agent}] {buildState.currentTask.file}
            </span>
          )}
        </div>
      )}

      {buildState.status === 'idle' && (
        <div className="flex-1" />
      )}

      {/* Agent status summary */}
      {agentCount > 0 && (
        <div className="flex items-center gap-3 flex-shrink-0 text-[11px]">
          {activeAgents > 0 && (
            <span className="flex items-center gap-1 text-teal">
              <span className="w-1.5 h-1.5 rounded-full bg-teal" />
              {activeAgents} running
            </span>
          )}
          {blockedAgents > 0 && (
            <span className="flex items-center gap-1 text-amber">
              <span className="w-1.5 h-1.5 rounded-full bg-amber" />
              {blockedAgents} blocked
            </span>
          )}
          {idleAgents > 0 && (
            <span className="flex items-center gap-1 text-slate-500">
              {idleAgents} idle
            </span>
          )}
        </div>
      )}

      {/* Pending replies */}
      {pendingCount > 0 && (
        <div className="flex items-center gap-1.5 bg-amber/10 border border-amber/30 rounded-full px-3 py-1 flex-shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
          <span className="text-xs text-amber font-medium">
            {pendingCount} waiting {pendingCount === 1 ? 'reply' : 'replies'}
          </span>
        </div>
      )}

      <a href="/classic" className="text-xs text-slate-500 hover:text-slate-300 px-2 py-1 rounded hover:bg-slate-800 flex-shrink-0">
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
