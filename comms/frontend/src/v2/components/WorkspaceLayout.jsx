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
   Center: Active workspace / file viewer / Agent Build Stage (flexible)
   Right : Agent Chat Panel (380px, primary focus)
   Bottom: Activity feed (minimizable)
*/

export function WorkspaceLayout() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [showFileViewer, setShowFileViewer] = useState(false)
  const [activityMinimized, setActivityMinimized] = useState(true)
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false)

  // Agent Build Stage state
  const [agentBuildReport, setAgentBuildReport] = useState(null)
  const [selectedAgent, setSelectedAgent] = useState(null)

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

    // ── Agent Build Stage ────────────────────────────────────────────
    if (event === 'agents_built') {
      setAgentBuildReport(payload.agents || {})
      setEvents(prev => [{
        id: crypto.randomUUID(), type: event,
        text: `Agent build complete — ${Object.keys(payload.agents || {}).length} agents ready`,
        time: new Date().toISOString()
      }, ...prev].slice(0, 200))
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

        {/* Center — Workspace / File Viewer / Agent Build Stage */}
        <div className="flex-1 min-w-0 overflow-hidden bg-fluent-bg">
          {selectedAgent && agentBuildReport ? (
            <AgentDetailCard
              agentId={selectedAgent}
              agent={agentBuildReport[selectedAgent]}
              onClose={() => setSelectedAgent(null)}
            />
          ) : agentBuildReport ? (
            <AgentBuildStage
              agents={agentBuildReport}
              onSelectAgent={setSelectedAgent}
              onDismiss={() => { setAgentBuildReport(null); setSelectedAgent(null); }}
            />
          ) : showFileViewer && selectedFile ? (
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

/* ═══════════════════════════════════════════════════════
   Agent Build Stage — Canvas showing agent bots
   ═══════════════════════════════════════════════════════ */

const AGENT_INFO = {
  supervisor:       { role: 'Orchestrator',       color: 'bg-violet',     bg: 'bg-violet/10',      border: 'border-violet/30',     icon: '👑', desc: 'Coordinates all agents, delegates tasks, reports progress to user' },
  architect:        { role: 'Architect',           color: 'bg-blue-400',   bg: 'bg-blue-400/10',    border: 'border-blue-400/30',   icon: '🏗️', desc: 'Analyzes requirements, designs system architecture, plans iterations' },
  planner:          { role: 'Planner',             color: 'bg-amber',      bg: 'bg-amber/10',       border: 'border-amber/30',      icon: '📋', desc: 'Decomposes iterations into file-level tasks, assigns agents' },
  backend_dev:      { role: 'Backend Dev',         color: 'bg-emerald',    bg: 'bg-emerald/10',     border: 'border-emerald/30',    icon: '⚙️', desc: 'Implements source code — any language, framework, or type' },
  test_dev:         { role: 'Test Dev',            color: 'bg-cyan-400',   bg: 'bg-cyan-400/10',    border: 'border-cyan-400/30',   icon: '🧪', desc: 'Writes unit and integration tests following TDD principles' },
  reviewer:         { role: 'Reviewer',            color: 'bg-rose',       bg: 'bg-rose/10',        border: 'border-rose/30',       icon: '🔍', desc: 'Reviews code for correctness, intent matching, and simplicity' },
  integration_test: { role: 'Integration Test',    color: 'bg-teal',       bg: 'bg-teal/10',        border: 'border-teal/30',       icon: '🔗', desc: 'Writes integration and E2E tests that verify components work together' },
  config_agent:     { role: 'Config',              color: 'bg-sky',        bg: 'bg-sky/10',         border: 'border-sky/30',        icon: '⚡', desc: 'Creates configuration files (JSON, YAML, TOML, env, etc.)' },
  docs_agent:       { role: 'Docs',                color: 'bg-indigo',     bg: 'bg-indigo/10',      border: 'border-indigo/30',     icon: '📝', desc: 'Writes documentation — README, API docs, usage guides' },
  cicd:             { role: 'CI/CD',               color: 'bg-orange',     bg: 'bg-orange/10',      border: 'border-orange/30',     icon: '🚀', desc: 'Sets up CI/CD pipelines, Docker, deployment infrastructure' },
  spec_agent:       { role: 'Spec',                color: 'bg-pink',       bg: 'bg-pink/10',        border: 'border-pink/30',       icon: '📐', desc: 'Writes technical specifications from project requirements' },
}

function AgentBuildStage({ agents, onSelectAgent, onDismiss }) {
  const agentEntries = Object.entries(agents)
  const readyCount = agentEntries.length

  return (
    <div className="h-full flex flex-col bg-fluent-bg overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="px-6 py-4 border-b border-fluent-borderSubtle flex items-center justify-between flex-shrink-0">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-fluent-lg bg-fluent-accentSubtle border border-fluent-accentBorder flex items-center justify-center">
              <span className="text-sm">🤖</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-fluent-text">Agent Build Stage</h2>
              <p className="text-xs text-fluent-textTert">{readyCount} agents prepared and ready</p>
            </div>
          </div>
        </div>
        <button onClick={onDismiss}
          className="p-2 rounded-fluent-md hover:bg-fluent-card text-fluent-textTert hover:text-fluent-textSec transition-colors"
          title="Dismiss">
          <CloseIcon />
        </button>
      </div>

      {/* Agent Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 max-w-6xl mx-auto">
          {agentEntries.map(([id, info]) => {
            const meta = AGENT_INFO[id] || { role: id, color: 'bg-zinc-400', bg: 'bg-zinc-400/10', border: 'border-zinc-400/30', icon: '🤖', desc: 'Agent' }
            return (
              <AgentBotCard
                key={id}
                id={id}
                info={info}
                meta={meta}
                onClick={() => onSelectAgent(id)}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}

function AgentBotCard({ id, info, meta, onClick }) {
  const [hovered, setHovered] = useState(false)

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`relative group flex flex-col items-start p-4 rounded-fluent-xl border transition-all duration-200 text-left
        ${meta.bg} ${meta.border} hover:shadow-fluent-elevated hover:scale-[1.02] active:scale-[0.98] animate-scale-in`}
    >
      {/* Bot avatar */}
      <div className={`w-12 h-12 rounded-fluent-lg ${meta.bg} border ${meta.border} flex items-center justify-center text-xl mb-3 transition-transform duration-200 group-hover:scale-110`}>
        {meta.icon}
      </div>

      {/* Name */}
      <p className="text-sm font-semibold text-fluent-text">{info.label || meta.role}</p>

      {/* Role */}
      <p className="text-xs text-fluent-textTert mt-0.5">{meta.role}</p>

      {/* Skills count */}
      {info.skills?.length > 0 && (
        <span className="mt-2 text-[10px] px-2 py-0.5 rounded-full bg-fluent-accentSubtle text-fluent-accent">
          {info.skills.length} skill{info.skills.length > 1 ? 's' : ''}
        </span>
      )}

      {/* Hover tooltip */}
      {hovered && (
        <div className="absolute -bottom-16 left-1/2 -translate-x-1/2 z-50 w-64 animate-slide-up">
          <div className="bg-fluent-card border border-fluent-border rounded-fluent-lg p-3 shadow-fluent-flyout">
            <div className="flex items-center gap-2 mb-1">
              <span>{meta.icon}</span>
              <span className="text-xs font-semibold text-fluent-text">{info.label}</span>
            </div>
            <p className="text-[11px] text-fluent-textSec leading-snug">{meta.desc}</p>
            <div className="mt-2 pt-2 border-t border-fluent-borderSubtle flex items-center justify-between">
              <span className="text-[10px] text-fluent-textTert">Prompt: {info.prompt_size_bytes}B</span>
              <span className="text-[10px] text-fluent-textTert">Click for details →</span>
            </div>
          </div>
        </div>
      )}
    </button>
  )
}

/* ═══════════════════════════════════════════════════════
   Agent Detail Card — Full details on click
   ═══════════════════════════════════════════════════════ */

function AgentDetailCard({ agentId, agent, onClose }) {
  const meta = AGENT_INFO[agentId] || { role: agentId, color: 'bg-zinc-400', bg: 'bg-zinc-400/10', border: 'border-zinc-400/30', icon: '🤖', desc: 'Agent' }

  return (
    <div className="h-full flex flex-col bg-fluent-bg overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="px-6 py-4 border-b border-fluent-borderSubtle flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={onClose}
            className="p-1.5 rounded-fluent-md hover:bg-fluent-card text-fluent-textTert hover:text-fluent-textSec transition-colors">
            <ChevronLeftIcon />
          </button>
          <div className={`w-10 h-10 rounded-fluent-lg ${meta.bg} border ${meta.border} flex items-center justify-center text-xl`}>
            {meta.icon}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-fluent-text">{agent.label}</h2>
            <p className="text-xs text-fluent-textTert">{meta.role}</p>
          </div>
        </div>
        <button onClick={onClose}
          className="p-2 rounded-fluent-md hover:bg-fluent-card text-fluent-textTert hover:text-fluent-textSec transition-colors">
          <CloseIcon />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-5">
          {/* Description */}
          <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-5">
            <h3 className="text-sm font-semibold text-fluent-text mb-2">Description</h3>
            <p className="text-sm text-fluent-textSec leading-relaxed">{meta.desc}</p>
          </div>

          {/* Prompt Details */}
          <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-5">
            <h3 className="text-sm font-semibold text-fluent-text mb-3">Prompt Configuration</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-fluent-textTert uppercase tracking-wider">Size</span>
                <span className="text-fluent-text font-mono">{agent.prompt_size_bytes?.toLocaleString()} B</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-fluent-textTert uppercase tracking-wider">Lines</span>
                <span className="text-fluent-text font-mono">{agent.prompt_lines}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-fluent-textTert uppercase tracking-wider">Framework</span>
                <span className="text-fluent-text">{agent.framework || 'default'}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-fluent-textTert uppercase tracking-wider">Persona</span>
                <span className="text-fluent-text">{agent.persona || 'none'}</span>
              </div>
            </div>
          </div>

          {/* Skills */}
          <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-5">
            <h3 className="text-sm font-semibold text-fluent-text mb-3">
              Skills ({agent.skills?.length || 0})
            </h3>
            {agent.skills?.length > 0 ? (
              <div className="space-y-2">
                {agent.skills.map((s, i) => (
                  <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-fluent-lg border ${
                    s.exists ? 'border-fluent-success/20 bg-fluent-success/5' : 'border-fluent-danger/20 bg-fluent-danger/5'
                  }`}>
                    <div className="flex items-center gap-2">
                      {s.exists ? (
                        <span className="w-2 h-2 rounded-full bg-fluent-success" />
                      ) : (
                        <span className="w-2 h-2 rounded-full bg-fluent-danger" />
                      )}
                      <span className="text-sm text-fluent-text font-mono">{s.file}</span>
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                      s.exists ? 'bg-fluent-success/10 text-fluent-success' : 'bg-fluent-danger/10 text-fluent-danger'
                    }`}>
                      {s.exists ? 'Found' : 'Missing'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fluent-textTert italic">No skills configured</p>
            )}
          </div>

          {/* Model */}
          <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-5">
            <h3 className="text-sm font-semibold text-fluent-text mb-2">Model</h3>
            <code className="text-sm text-fluent-accent font-mono">{agent.model}</code>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════
   Icons
   ═══════════════════════════════════════════ */

function ChevronLeftIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function TerminalIcon() {
  return (
    <svg className="w-4 h-4 text-fluent-accent" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
