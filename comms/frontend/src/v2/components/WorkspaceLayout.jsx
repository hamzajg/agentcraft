import { useState, useEffect, useCallback, useRef } from 'react'
import { FileExplorer } from './FileExplorer'
import { FileViewer } from './FileViewer'
import { AgentPanel } from './AgentPanel'
import { ActivityPanel } from './ActivityPanel'
import { useWebSocket } from '../../hooks/useWebSocket'
import { api } from '../../lib/api'

/* ─── Fluent UI v2 Workspace Layout ───
   Chat-centric responsive 3-panel design:
   Left  : File Explorer (collapsible, 260px)
   Center: Active workspace / file viewer (flexible)
   Right : Agent Chat Panel (380px, primary focus)
   Bottom: Activity feed (minimizable)
*/

export function WorkspaceLayout() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [showFileViewer, setShowFileViewer] = useState(false)
  const [activityMinimized, setActivityMinimized] = useState(true)
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false)

  const [channels, setChannels] = useState([])
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState({})
  const [activeAgent, setActiveAgent] = useState(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [sending, setSending] = useState(false)
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState([])
  const [busMessages, setBusMessages] = useState([])

  // Build progress state
  const [buildState, setBuildState] = useState({
    status: 'idle',
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

    // Clarification messages (agent → human)
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

    // Agent status updates
    if (event === 'agent_status') {
      setStatuses(prev => ({ ...prev, [payload.agent_id]: payload.status }))
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: `${payload.agent_id} → ${payload.status}`, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Log messages
    if (event === 'log') {
      const id = payload.id || crypto.randomUUID()
      setEvents(prev => [{ id, type: event, agent_id: payload.agent_id, text: payload.message?.slice(0, 120) || 'Log entry', time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Agent-to-Agent bus messages
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

      setBusMessages(prev => [{
        id, type: event, from_agent: fromAgent, to_agent: toAgent,
        content: payload.content, text, time: new Date().toISOString(),
      }, ...prev].slice(0, 100))

      setEvents(prev => [{ id, type: event, agent_id: fromAgent, text, time: new Date().toISOString() }, ...prev].slice(0, 200))
      return
    }

    // Build progress tracking
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

    // Generic catch for remaining build events
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
              if (x.id === m.id && x.status === 'replied') return x
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
            merged[idx] = m
          } else if (m.status !== 'replied' && merged[idx].status === 'replied') {
            // Keep replied status
          } else {
            merged[idx] = m
          }
        }
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

  const loadAgentMessages = useCallback(async (agentId) => {
    try {
      const msgs = await api.messages(agentId, 100)
      if (msgs && msgs.length > 0) {
        setMessages(prev => {
          const existing = prev[agentId] ?? []
          const merged = [...existing]
          for (const m of msgs) {
            const idx = merged.findIndex(x => x.id === m.id)
            if (idx < 0) {
              merged.push(m)
            } else if (m.status !== merged[idx].status) {
              merged[idx] = m
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
    <div className="h-screen flex flex-col bg-fluent-bg overflow-hidden font-sans">
      {/* ─── Top Bar ─── */}
      <TopBar
        connected={connected}
        pendingCount={pendingCount}
        agentCount={channels?.length || 0}
        statuses={statuses}
        buildState={buildState}
        onToggleLeftPanel={() => setLeftPanelCollapsed(p => !p)}
        leftPanelCollapsed={leftPanelCollapsed}
      />

      {/* ─── Main Content Area ─── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel — File Explorer */}
        <div
          className={`flex-shrink-0 border-r border-fluent-borderSubtle bg-fluent-surface transition-all duration-200 ease-ease overflow-hidden ${
            leftPanelCollapsed ? 'w-0 border-r-0' : 'w-[260px]'
          }`}
        >
          <FileExplorer onFileSelect={handleFileSelect} />
        </div>

        {/* Center — Workspace / File Viewer */}
        <div className="flex-1 min-w-0 overflow-hidden bg-fluent-bg">
          {showFileViewer && selectedFile ? (
            <FileViewer file={selectedFile} onClose={handleCloseFile} />
          ) : (
            <FluentEmptyState onFileClick={() => setLeftPanelCollapsed(false)} />
          )}
        </div>

        {/* Right Panel — Agent Chat (primary focus) */}
        <div className="w-[380px] min-w-[320px] max-w-[480px] flex-shrink-0 overflow-hidden border-l border-fluent-borderSubtle bg-fluent-surface">
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

      {/* ─── Bottom Activity Panel ─── */}
      <ActivityPanel
        events={events}
        onMinimize={setActivityMinimized}
      />
    </div>
  )
}

/* ═══════════════════════════════════════════
   TopBar — Fluent UI styled header
   ═══════════════════════════════════════════ */

function TopBar({ connected, pendingCount, agentCount, statuses, buildState, onToggleLeftPanel, leftPanelCollapsed }) {
  const activeAgents = Object.entries(statuses).filter(([, s]) => s === 'running').length
  const blockedAgents = Object.entries(statuses).filter(([, s]) => s === 'blocked').length

  return (
    <header className="h-12 flex-shrink-0 bg-fluent-surfaceAlt border-b border-fluent-border flex items-center px-3 gap-2">
      {/* Logo + toggle */}
      <button
        onClick={onToggleLeftPanel}
        className="flex items-center gap-2 hover:bg-fluent-card rounded-fluent-md px-2 py-1.5 transition-colors"
        title={leftPanelCollapsed ? 'Show file explorer' : 'Hide file explorer'}
      >
        <div className="w-7 h-7 rounded-fluent-md bg-fluent-accentSubtle border border-fluent-accentBorder flex items-center justify-center">
          <TerminalIcon />
        </div>
        <span className="font-semibold text-sm text-fluent-text">AgentCraft</span>
      </button>

      {/* Divider */}
      <div className="w-px h-5 bg-fluent-borderSubtle" />

      {/* Connection status */}
      <div className="flex items-center gap-1.5 px-1">
        <span className={`w-2 h-2 rounded-full transition-colors ${connected ? 'bg-fluent-success' : 'bg-fluent-danger animate-pulse'}`} />
        <span className="text-[11px] text-fluent-textTert">{connected ? 'Connected' : 'Reconnecting…'}</span>
      </div>

      {/* Build progress */}
      {buildState.status !== 'idle' && (
        <>
          <div className="w-px h-5 bg-fluent-borderSubtle" />
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <BuildBadge buildState={buildState} />

            {buildState.currentPhase && (
              <span className="text-xs text-fluent-textSec truncate">
                Phase {buildState.currentPhase}
                {buildState.currentIteration && <span className="text-fluent-textTert mx-1">›</span>}
                {buildState.currentIteration && `Iter ${buildState.currentIteration}`}
              </span>
            )}

            {(buildState.approvedCount > 0 || buildState.rejectedCount > 0) && (
              <div className="flex items-center gap-2 flex-shrink-0">
                {buildState.approvedCount > 0 && (
                  <span className="text-xs text-fluent-success font-medium">✓ {buildState.approvedCount}</span>
                )}
                {buildState.rejectedCount > 0 && (
                  <span className="text-xs text-fluent-warning font-medium">✗ {buildState.rejectedCount}</span>
                )}
              </div>
            )}

            {buildState.currentTask && (
              <span className="text-xs text-fluent-textTert truncate font-mono">
                [{buildState.currentTask.agent}] {buildState.currentTask.file}
              </span>
            )}
          </div>
        </>
      )}

      {buildState.status === 'idle' && <div className="flex-1" />}

      {/* Agent status summary */}
      {agentCount > 0 && (
        <div className="flex items-center gap-3 flex-shrink-0 text-[11px]">
          {activeAgents > 0 && (
            <span className="flex items-center gap-1 text-fluent-success">
              <span className="w-1.5 h-1.5 rounded-full bg-fluent-success animate-pulse" />
              {activeAgents}
            </span>
          )}
          {blockedAgents > 0 && (
            <span className="flex items-center gap-1 text-fluent-warning">
              <span className="w-1.5 h-1.5 rounded-full bg-fluent-warning" />
              {blockedAgents}
            </span>
          )}
        </div>
      )}

      {/* Pending replies badge */}
      {pendingCount > 0 && (
        <button
          className="flex items-center gap-1.5 bg-fluent-warningBg border border-fluent-warningBorder rounded-fluent-lg px-2.5 py-1 flex-shrink-0 transition-transform hover:scale-[1.02] active:scale-[0.98]"
          title="Pending replies waiting"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-fluent-warning animate-pulse" />
          <span className="text-xs text-fluent-warning font-semibold">
            {pendingCount}
          </span>
        </button>
      )}

      {/* Classic UI link */}
      <a href="/classic" className="text-xs text-fluent-textTert hover:text-fluent-textSec px-2 py-1 rounded-fluent-md hover:bg-fluent-card transition-colors flex-shrink-0">
        Classic
      </a>
    </header>
  )
}

function BuildBadge({ buildState }) {
  const config = {
    running:  { bg: 'bg-fluent-success/10', text: 'text-fluent-success', dot: 'bg-fluent-success animate-pulse', label: 'Running' },
    done:     { bg: 'bg-fluent-success/10', text: 'text-fluent-success', dot: 'bg-fluent-success', label: 'Done' },
    paused:   { bg: 'bg-fluent-card', text: 'text-fluent-textSec', dot: 'bg-fluent-textTert', label: 'Paused' },
    stopped:  { bg: 'bg-fluent-danger/10', text: 'text-fluent-danger', dot: 'bg-fluent-danger', label: 'Stopped' },
    error:    { bg: 'bg-fluent-danger/10', text: 'text-fluent-danger', dot: 'bg-fluent-danger', label: 'Error' },
  }
  const c = config[buildState.status] || config.running

  return (
    <span className={`flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  )
}

/* ═══════════════════════════════════════════
   Fluent Empty State — Center workspace
   ═══════════════════════════════════════════ */

function FluentEmptyState({ onFileClick }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-fluent-textTert p-8 animate-fade-in">
      {/* Decorative icon */}
      <div className="w-20 h-20 mb-6 rounded-fluent-xl bg-fluent-card border border-fluent-border flex items-center justify-center shadow-fluent-card">
        <svg className="w-10 h-10 text-fluent-textTert" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          <line x1="12" y1="11" x2="12" y2="17" />
          <line x1="9" y1="14" x2="15" y2="14" />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-fluent-textSec mb-2">AgentCraft Workspace</h2>
      <p className="text-sm text-fluent-textTert text-center max-w-md mb-6 leading-relaxed">
        Browse project files, communicate with agents, and monitor activity in real-time.
      </p>

      {/* File category chips */}
      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-fluent-accentSubtle text-fluent-accent">
          <span className="w-2 h-2 rounded-full bg-fluent-accent" />
          Documentation
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-fluent-warningBg text-fluent-warning">
          <span className="w-2 h-2 rounded-full bg-fluent-warning" />
          Workflow
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-fluent-success/10 text-fluent-success">
          <span className="w-2 h-2 rounded-full bg-fluent-success" />
          Generated Code
        </span>
      </div>

      {/* Quick action */}
      <button
        onClick={onFileClick}
        className="mt-6 text-xs px-4 py-2 rounded-fluent-lg bg-fluent-card border border-fluent-border text-fluent-textSec hover:bg-fluent-cardHover hover:text-fluent-text transition-colors shadow-fluent-card"
      >
        Open File Explorer
      </button>
    </div>
  )
}

/* ═══════════════════════════════════════════
   Icons
   ═══════════════════════════════════════════ */

function TerminalIcon() {
  return (
    <svg className="w-4 h-4 text-fluent-accent" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
