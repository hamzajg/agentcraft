import { useState, useEffect, useCallback, useRef } from 'react'
import { FileExplorer } from './FileExplorer'
import { FileViewer } from './FileViewer'
import { AgentPanel } from './AgentPanel'
import { ActivityPanel } from './ActivityPanel'
import { useWebSocket } from '../../hooks/useWebSocket'
import { api } from '../../lib/api'

/* ─── Fluent UI v2 Workspace Layout ───
   Two-view design:
   Left  : File Explorer (collapsible, 260px)
   Center: File Viewer / Empty State (main view)
   Right : Agent Chat Panel (380px)
   Overlay: Agent Build Stage (slides in from right, dismissible)
   Bottom: Activity feed (minimizable)
*/

export function WorkspaceLayout() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [showFileViewer, setShowFileViewer] = useState(false)
  const [activityMinimized, setActivityMinimized] = useState(true)
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false)

  // Agent Build Stage — collapsible overlay panel
  const [agentBuildReport, setAgentBuildReport] = useState(null)
  const [showBuildPanel, setShowBuildPanel] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState(null)

  // Poll for agent build report until data arrives
  useEffect(() => {
    let cancelled = false
    let attempts = 0
    const maxAttempts = 15
    const poll = async () => {
      if (cancelled) return
      attempts++
      try {
        const data = await api.agentBuildReport()
        if (data && data.agents && Object.keys(data.agents).length > 0) {
          if (!cancelled) {
            setAgentBuildReport(data.agents)
            setShowBuildPanel(true) // Auto-open on first receipt
          }
          return
        }
      } catch (e) { /* ignore */ }
      if (attempts >= maxAttempts) { if (!cancelled) setAgentBuildReport(null); return }
      if (!cancelled) setTimeout(poll, 2000)
    }
    poll()
    return () => { cancelled = true }
  }, [])

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
        hasBuildReport={!!agentBuildReport}
        showBuildPanel={showBuildPanel}
        onToggleBuildPanel={() => setShowBuildPanel(p => !p)}
      />

      {/* ─── Main Content Area ─── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel — File Explorer */}
        <div
          className={`flex-shrink-0 border-r border-fluent-borderSubtle bg-fluent-surface transition-all duration-200 overflow-hidden ${
            leftPanelCollapsed ? 'w-0 border-r-0' : 'w-[260px]'
          }`}
        >
          <FileExplorer onFileSelect={handleFileSelect} />
        </div>

        {/* Center — File Viewer (main view) + Agent Build Overlay */}
        <div className="flex-1 min-w-0 overflow-hidden bg-fluent-bg relative">
          {selectedFile && showFileViewer ? (
            <FileViewer file={selectedFile} onClose={handleCloseFile} />
          ) : (
            <FluentEmptyState onFileClick={() => setLeftPanelCollapsed(false)} />
          )}

          {/* Agent Build Stage — Slide-in overlay panel */}
          {showBuildPanel && agentBuildReport && (
            <AgentBuildOverlay
              agents={agentBuildReport}
              selectedAgent={selectedAgent}
              onSelectAgent={setSelectedAgent}
              onClose={() => { setShowBuildPanel(false); setSelectedAgent(null); }}
            />
          )}
        </div>

        {/* Right Panel — Agent Chat */}
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

function TopBar({ connected, pendingCount, agentCount, statuses, buildState, onToggleLeftPanel, leftPanelCollapsed, hasBuildReport, showBuildPanel, onToggleBuildPanel }) {
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

      {/* Agent Build Stage toggle */}
      {hasBuildReport && (
        <button
          onClick={onToggleBuildPanel}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-fluent-lg text-xs font-medium transition-all duration-200 flex-shrink-0 ${
            showBuildPanel
              ? 'bg-fluent-accentSubtle border border-fluent-accentBorder text-fluent-accent'
              : 'bg-fluent-card border border-fluent-borderSubtle text-fluent-textSec hover:text-fluent-text hover:bg-fluent-cardHover'
          }`}
          title="Toggle Agent Build Stage"
        >
          <span>🤖</span>
          Agents
          {!showBuildPanel && (
            <span className="w-1.5 h-1.5 rounded-full bg-fluent-accent animate-pulse" />
          )}
        </button>
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
   Agent Build Overlay — Slide-in panel from right
   ═══════════════════════════════════════════════════════ */

const AGENT_META = {
  supervisor:       { role: 'Orchestrator',       icon: '👑', desc: 'Coordinates all agents, delegates tasks, reports progress to user', bg: 'bg-violet/10', border: 'border-violet/30' },
  architect:        { role: 'Architect',           icon: '🏗️', desc: 'Analyzes requirements, designs system architecture, plans iterations', bg: 'bg-blue-400/10', border: 'border-blue-400/30' },
  planner:          { role: 'Planner',             icon: '📋', desc: 'Decomposes iterations into file-level tasks, assigns agents', bg: 'bg-amber/10', border: 'border-amber/30' },
  backend_dev:      { role: 'Backend Dev',         icon: '⚙️', desc: 'Implements source code — any language, framework, or type', bg: 'bg-emerald/10', border: 'border-emerald/30' },
  test_dev:         { role: 'Test Dev',            icon: '🧪', desc: 'Writes unit and integration tests following TDD principles', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30' },
  reviewer:         { role: 'Reviewer',            icon: '🔍', desc: 'Reviews code for correctness, intent matching, and simplicity', bg: 'bg-rose/10', border: 'border-rose/30' },
  integration_test: { role: 'Integration Test',    icon: '🔗', desc: 'Writes integration and E2E tests that verify components work together', bg: 'bg-teal/10', border: 'border-teal/30' },
  config_agent:     { role: 'Config',              icon: '⚡', desc: 'Creates configuration files (JSON, YAML, TOML, env, etc.)', bg: 'bg-sky/10', border: 'border-sky/30' },
  docs_agent:       { role: 'Docs',                icon: '📝', desc: 'Writes documentation — README, API docs, usage guides', bg: 'bg-indigo/10', border: 'border-indigo/30' },
  cicd:             { role: 'CI/CD',               icon: '🚀', desc: 'Sets up CI/CD pipelines, Docker, deployment infrastructure', bg: 'bg-orange/10', border: 'border-orange/30' },
  spec_agent:       { role: 'Spec',                icon: '📐', desc: 'Writes technical specifications from project requirements', bg: 'bg-pink/10', border: 'border-pink/30' },
}

function AgentBuildOverlay({ agents, selectedAgent, onSelectAgent, onClose }) {
  const entries = Object.entries(agents)

  return (
    <div className="absolute inset-0 z-30 flex justify-end">
      {/* Backdrop — click to close */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" onClick={onClose} />

      {/* Panel */}
      <div className="relative w-[520px] max-w-full h-full bg-fluent-surface border-l border-fluent-borderSubtle shadow-fluent-flyout flex flex-col animate-slide-right">
        {/* Header */}
        <div className="px-5 py-3 border-b border-fluent-borderSubtle flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-fluent-lg bg-fluent-accentSubtle border border-fluent-accentBorder flex items-center justify-center text-base">🤖</div>
            <div>
              <h2 className="text-sm font-semibold text-fluent-text">Agent Build Stage</h2>
              <p className="text-[11px] text-fluent-textTert">{entries.length} agents ready</p>
            </div>
          </div>
          <button onClick={onClose}
            className="p-1.5 rounded-fluent-md hover:bg-fluent-card text-fluent-textTert hover:text-fluent-textSec transition-colors">
            <CloseIcon />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {selectedAgent ? (
            /* ── Detail View ── */
            <AgentAgentDetail
              agentId={selectedAgent}
              agent={agents[selectedAgent]}
              onBack={() => onSelectAgent(null)}
            />
          ) : (
            /* ── Grid View ── */
            <div className="grid grid-cols-2 gap-3">
              {entries.map(([id, info]) => {
                const meta = AGENT_META[id] || { role: id, icon: '🤖', desc: 'Agent', bg: 'bg-zinc-400/10', border: 'border-zinc-400/30' }
                return (
                  <button key={id} onClick={() => onSelectAgent(id)}
                    className={`flex flex-col items-start p-3.5 rounded-fluent-xl border transition-all duration-150 text-left
                      ${meta.bg} ${meta.border} hover:shadow-fluent-elevated hover:scale-[1.02] active:scale-[0.97]`}>
                    <div className={`w-10 h-10 rounded-fluent-lg ${meta.bg} border ${meta.border} flex items-center justify-center text-lg mb-2.5 transition-transform group-hover:scale-110`}>
                      {meta.icon}
                    </div>
                    <p className="text-sm font-semibold text-fluent-text">{info.label || meta.role}</p>
                    <p className="text-[11px] text-fluent-textTert mt-0.5">{meta.role}</p>
                    {info.skills?.length > 0 && (
                      <span className="mt-2 text-[10px] px-2 py-0.5 rounded-full bg-fluent-accentSubtle text-fluent-accent">
                        {info.skills.length} skill{info.skills.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function AgentAgentDetail({ agentId, agent, onBack }) {
  const meta = AGENT_META[agentId] || { role: agentId, icon: '🤖', desc: 'Agent', bg: 'bg-zinc-400/10', border: 'border-zinc-400/30' }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Back button */}
      <button onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-fluent-textSec hover:text-fluent-text px-1 py-1 rounded-fluent-md hover:bg-fluent-card transition-colors">
        <ChevronLeftIcon />Back
      </button>

      {/* Avatar + Name */}
      <div className="flex items-center gap-3">
        <div className={`w-14 h-14 rounded-fluent-xl ${meta.bg} border ${meta.border} flex items-center justify-center text-2xl`}>
          {meta.icon}
        </div>
        <div>
          <h3 className="text-base font-bold text-fluent-text">{agent.label}</h3>
          <p className="text-xs text-fluent-textTert">{meta.role}</p>
        </div>
      </div>

      {/* Description */}
      <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-4">
        <p className="text-sm text-fluent-textSec leading-relaxed">{meta.desc}</p>
      </div>

      {/* Prompt Config */}
      <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-4">
        <h4 className="text-xs font-semibold text-fluent-textTert uppercase tracking-wider mb-3">Prompt</h4>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="text-[10px] text-fluent-textTert">Size</span><p className="text-fluent-text font-mono">{agent.prompt_size_bytes?.toLocaleString()} B</p></div>
          <div><span className="text-[10px] text-fluent-textTert">Lines</span><p className="text-fluent-text font-mono">{agent.prompt_lines}</p></div>
          <div><span className="text-[10px] text-fluent-textTert">Framework</span><p className="text-fluent-text">{agent.framework || 'default'}</p></div>
          <div><span className="text-[10px] text-fluent-textTert">Persona</span><p className="text-fluent-text">{agent.persona || 'none'}</p></div>
        </div>
      </div>

      {/* Skills */}
      <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-4">
        <h4 className="text-xs font-semibold text-fluent-textTert uppercase tracking-wider mb-3">Skills ({agent.skills?.length || 0})</h4>
        {agent.skills?.length > 0 ? (
          <div className="space-y-1.5">
            {agent.skills.map((s, i) => (
              <div key={i} className={`flex items-center justify-between px-3 py-1.5 rounded-fluent-lg border text-sm ${
                s.exists ? 'border-fluent-success/20 bg-fluent-success/5' : 'border-fluent-danger/20 bg-fluent-danger/5'
              }`}>
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${s.exists ? 'bg-fluent-success' : 'bg-fluent-danger'}`} />
                  <span className="text-fluent-text font-mono text-xs">{s.file}</span>
                </div>
                <span className={`text-[10px] px-1.5 py-px rounded-full ${s.exists ? 'bg-fluent-success/10 text-fluent-success' : 'bg-fluent-danger/10 text-fluent-danger'}`}>
                  {s.exists ? 'Found' : 'Missing'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-fluent-textTert italic">No skills</p>
        )}
      </div>

      {/* Model */}
      <div className="rounded-fluent-xl border border-fluent-borderSubtle bg-fluent-surfaceAlt p-4">
        <h4 className="text-xs font-semibold text-fluent-textTert uppercase tracking-wider mb-2">Model</h4>
        <code className="text-sm text-fluent-accent font-mono">{agent.model}</code>
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
