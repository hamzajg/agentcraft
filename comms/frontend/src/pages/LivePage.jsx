import { useState, useEffect, useRef, useCallback } from 'react'

const POLL_MS = 1500

// ── Event type config ────────────────────────────────────────────────────────
const EV = {
  build_started:    { color: 'text-teal',   icon: '▶', label: 'Build started'   },
  build_done:       { color: 'text-teal',   icon: '✓', label: 'Build complete'  },
  phase_started:    { color: 'text-accent', icon: '◈', label: 'Phase'           },
  iter_started:     { color: 'text-accent', icon: '○', label: 'Iteration'       },
  iter_done:        { color: 'text-accent', icon: '●', label: 'Iteration done'  },
  task_started:     { color: 'text-amber',  icon: '→', label: 'Task'            },
  task_done:        { color: 'text-amber',  icon: '✓', label: 'Task done'       },
  aider_token:      { color: 'text-muted',  icon: ' ', label: ''                },
  aider_done:       { color: 'text-muted',  icon: '·', label: 'Aider done'      },
  file_written:     { color: 'text-teal',   icon: '⬡', label: 'File written'    },
  reviewer_verdict: { color: 'text-amber',  icon: '◎', label: 'Reviewer'        },
  approval_gate:    { color: 'text-accent', icon: '⬡', label: 'Approval gate'   },
  directive_injected:{ color: 'text-accent',icon: '→', label: 'Directive'       },
  paused:           { color: 'text-amber',  icon: '⏸', label: 'Paused'          },
  resumed:          { color: 'text-teal',   icon: '▶', label: 'Resumed'         },
  stopped:          { color: 'text-danger', icon: '⏹', label: 'Stopped'         },
  error:            { color: 'text-danger', icon: '✗', label: 'Error'           },
}

const AGENT_COLORS = {
  spec:             'text-blue-400',
  architect:        'text-purple-400',
  planner:          'text-pink-400',
  backend_dev:      'text-teal',
  test_dev:         'text-cyan-400',
  reviewer:         'text-amber',
  config_agent:     'text-green-400',
  docs_agent:       'text-indigo-400',
  integration_test: 'text-orange-400',
  cicd:             'text-gray-400',
}

export function LivePage() {
  const [events,      setEvents]     = useState([])
  const [state,       setState]      = useState({})
  const [activeAgent, setActiveAgent]= useState(null)
  const [tokenBuf,    setTokenBuf]   = useState({})   // agent → [lines]
  const [peekFile,    setPeekFile]   = useState(null)
  const [peekContent, setPeekContent]= useState('')
  const [directive,   setDirective]  = useState('')
  const [rejectReason,setRejectReason]= useState('')
  const [gatesEnabled,setGatesEnabled]= useState(true)
  const [sinceTs,     setSinceTs]    = useState(0)
  const streamRef = useRef(null)
  const bottomRef = useRef(null)

  // ── Load events (polling + WS) ────────────────────────────────────────────
  const loadEvents = useCallback(async () => {
    try {
      const url = sinceTs > 0
        ? `/api/live/events?since=${sinceTs}`
        : '/api/live/events?limit=300'
      const newEvs = await fetch(url).then(r => r.json())
      if (Array.isArray(newEvs) && newEvs.length > 0) {
        setEvents(prev => {
          const ids = new Set(prev.map(e => e.id))
          const fresh = newEvs.filter(e => !ids.has(e.id))
          if (!fresh.length) return prev
          // Process token events → buffer per agent
          fresh.forEach(e => {
            if (e.type === 'aider_token' && e.data?.agent) {
              setTokenBuf(buf => ({
                ...buf,
                [e.data.agent]: [...(buf[e.data.agent] || []).slice(-400), e.data.text]
              }))
              setActiveAgent(e.data.agent)
            }
            if (e.type === 'aider_done') {
              // Keep last stream but mark done
            }
          })
          const last = newEvs[newEvs.length - 1]
          if (last) setSinceTs(last.ts)
          return [...prev, ...fresh].slice(-500)
        })
      }
    } catch {}
  }, [sinceTs])

  const loadState = useCallback(async () => {
    try {
      const s = await fetch('/api/live/state').then(r => r.json())
      setState(s)
    } catch {}
  }, [])

  useEffect(() => {
    loadEvents()
    loadState()
    const t1 = setInterval(loadEvents, POLL_MS)
    const t2 = setInterval(loadState, 2000)
    return () => { clearInterval(t1); clearInterval(t2) }
  }, [loadEvents, loadState])

  // WS for real-time push
  useEffect(() => {
    const ws = new WebSocket(`ws://${location.host}/ws`)
    ws.onmessage = e => {
      try {
        const { event, payload } = JSON.parse(e.data)
        if (event === 'aider_token' && payload?.data?.agent) {
          const agent = payload.data.agent
          const text  = payload.data.text || ''
          setTokenBuf(buf => ({
            ...buf,
            [agent]: [...(buf[agent] || []).slice(-400), text]
          }))
          setActiveAgent(agent)
        }
        // For non-token events: let poll pick them up (avoids dedup complexity)
      } catch {}
    }
    return () => ws.close()
  }, [])

  // Auto-scroll token stream
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [tokenBuf])

  // ── File peek ─────────────────────────────────────────────────────────────
  const peekFileContent = async (path) => {
    setPeekFile(path)
    try {
      const r = await fetch(`/api/live/file?path=${encodeURIComponent(path)}`).then(r => r.json())
      setPeekContent(r.content || '')
    } catch {
      setPeekContent('(file not readable)')
    }
  }

  // Poll peek file while agent is running
  useEffect(() => {
    if (!peekFile) return
    const t = setInterval(() => peekFileContent(peekFile), 2000)
    return () => clearInterval(t)
  }, [peekFile])

  // ── Control actions ───────────────────────────────────────────────────────
  const ctrl = async (endpoint, body = {}) => {
    await fetch(`/api/control/${endpoint}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).catch(() => {})
    loadState()
  }

  const sendDirective = async () => {
    if (!directive.trim()) return
    await ctrl('directive', { text: directive })
    setDirective('')
  }

  const approveIter = async (id) => await ctrl('approve', { iteration_id: id })
  const rejectIter  = async (id) => await ctrl('reject', { iteration_id: id, reason: rejectReason || 'Rejected by user' })

  // ── Derived state ─────────────────────────────────────────────────────────
  const nonTokenEvents = events.filter(e => e.type !== 'aider_token')
  const pendingGate    = nonTokenEvents.slice().reverse().find(e => e.type === 'approval_gate')
  const currentTokens  = activeAgent ? (tokenBuf[activeAgent] || []) : []
  const buildRunning   = state.build_running
  const paused         = state.paused
  const stopped        = state.stopped

  return (
    <div className="flex-1 flex overflow-hidden">

      {/* ── Left: Timeline ─────────────────────────────────────────────────── */}
      <div className="w-64 flex-shrink-0 border-r border-border flex flex-col bg-panel">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-xs font-semibold text-gray-200">Build Timeline</p>
          <p className="text-[10px] text-muted mt-0.5">
            {buildRunning && !paused && <span className="text-teal">● Running</span>}
            {paused  && <span className="text-amber">⏸ Paused</span>}
            {stopped && <span className="text-danger">⏹ Stopped</span>}
            {!buildRunning && !paused && !stopped && <span className="text-muted">Idle</span>}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5 text-[11px] font-mono">
          {nonTokenEvents.map((e, i) => {
            const cfg = EV[e.type] || { color: 'text-muted', icon: '·', label: e.type }
            const ts  = new Date(e.ts * 1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})
            const label = e.type === 'task_started'
              ? `${e.data?.agent}: ${(e.data?.file || '').split('/').pop()}`
              : e.type === 'iter_started'
                ? `Iter ${e.data?.id}: ${e.data?.name || ''}`
                : e.type === 'file_written'
                  ? (e.data?.path || '').split('/').pop()
                  : cfg.label

            const isFile = e.type === 'file_written'
            return (
              <div key={e.id || i}
                   onClick={() => isFile && peekFileContent(e.data?.path)}
                   className={`flex items-start gap-1.5 px-2 py-0.5 rounded
                     ${isFile ? 'cursor-pointer hover:bg-white/10' : ''}
                     ${e.type === 'approval_gate' ? 'bg-accent/10 border border-accent/30 rounded' : ''}`}>
                <span className={`shrink-0 ${cfg.color}`}>{cfg.icon}</span>
                <span className={`flex-1 truncate ${cfg.color}`}>{label}</span>
                <span className="text-muted text-[9px] shrink-0">{ts}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Centre: Token stream + approval gate ───────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Agent header */}
        <div className="px-5 py-3 border-b border-border flex items-center gap-3 flex-shrink-0">
          {activeAgent
            ? <>
                <span className={`text-sm font-semibold ${AGENT_COLORS[activeAgent] || 'text-gray-200'}`}>
                  {activeAgent.replace(/_/g, ' ')}
                </span>
                <span className="text-xs text-muted">live output</span>
                <button onClick={() => { setActiveAgent(null); setTokenBuf({}) }}
                  className="ml-auto text-[10px] text-muted hover:text-gray-400 px-2 py-0.5 border border-border rounded">
                  clear
                </button>
              </>
            : <span className="text-sm text-muted">Waiting for agent activity…</span>
          }
        </div>

        {/* Token stream */}
        <div className="flex-1 overflow-y-auto px-5 py-3 font-mono text-xs leading-relaxed bg-[#080a0d]"
             ref={streamRef}>
          {currentTokens.length === 0 && (
            <div className="text-muted text-center py-12">
              {buildRunning
                ? 'Agent is thinking…'
                : 'Start a build to see live output'}
            </div>
          )}
          {currentTokens.map((line, i) => (
            <div key={i} className={`${
              line.startsWith('>>') ? 'text-teal' :
              line.startsWith('APPROVED') ? 'text-teal font-bold' :
              line.startsWith('REWORK')   ? 'text-amber font-bold' :
              line.startsWith('ERROR') || line.startsWith('error:') ? 'text-danger' :
              'text-gray-300'
            }`}>{line || '\u00a0'}</div>
          ))}
          <div ref={bottomRef}/>
        </div>

        {/* Approval gate */}
        {pendingGate && (
          <div className="border-t border-accent/30 bg-accent/5 px-5 py-4 flex-shrink-0">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-accent">
                  ⬡ Approval gate — Iteration {pendingGate.data?.iteration_id}
                </p>
                <p className="text-xs text-muted mt-0.5">
                  {pendingGate.data?.summary || 'Review the iteration output before proceeding.'}
                </p>
              </div>
              <div className="flex gap-2 items-start flex-shrink-0">
                <input
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  placeholder="Reject reason (optional)"
                  className="text-xs bg-surface border border-border rounded px-3 py-1.5
                             text-gray-200 placeholder:text-muted focus:outline-none
                             focus:border-accent/40 w-48 font-mono"
                />
                <button
                  onClick={() => rejectIter(pendingGate.data?.iteration_id)}
                  className="text-xs px-3 py-1.5 border border-danger/50 text-danger
                             rounded hover:bg-danger/10 transition-colors">
                  ✗ Reject
                </button>
                <button
                  onClick={() => approveIter(pendingGate.data?.iteration_id)}
                  className="text-xs px-4 py-1.5 bg-teal text-black font-medium
                             rounded hover:opacity-90 transition-opacity">
                  ✓ Approve
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Right: Controls + file peek ────────────────────────────────────── */}
      <div className="w-72 flex-shrink-0 border-l border-border flex flex-col">

        {/* Control bar */}
        <div className="px-4 py-3 border-b border-border">
          <p className="text-[10px] font-mono text-muted uppercase tracking-wide mb-2">Controls</p>
          <div className="grid grid-cols-2 gap-1.5">
            <CtrlBtn onClick={() => ctrl('pause')}    disabled={paused || stopped}
                     color="amber" icon="⏸" label="Pause task"   />
            <CtrlBtn onClick={() => ctrl('pause-iter')} disabled={paused || stopped}
                     color="amber" icon="⏸" label="Pause iter"   />
            <CtrlBtn onClick={() => ctrl('resume')}   disabled={!paused}
                     color="teal"  icon="▶" label="Resume"       />
            <CtrlBtn onClick={() => ctrl('stop')}     disabled={stopped}
                     color="danger" icon="⏹" label="Stop"        />
          </div>

          {/* Gates toggle */}
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={() => {
                const next = !gatesEnabled
                setGatesEnabled(next)
                ctrl('gates', { enabled: next })
              }}
              className={`w-8 h-4 rounded-full transition-colors ${
                gatesEnabled ? 'bg-accent' : 'bg-border'
              } relative`}>
              <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
                gatesEnabled ? 'left-4' : 'left-0.5'
              }`}/>
            </button>
            <span className="text-[11px] text-muted">Approval gates</span>
          </div>
        </div>

        {/* Directive input */}
        <div className="px-4 py-3 border-b border-border">
          <p className="text-[10px] font-mono text-muted uppercase tracking-wide mb-2">
            Directive → next task
          </p>
          <textarea
            value={directive}
            onChange={e => setDirective(e.target.value)}
            placeholder="e.g. Use CompletableFuture instead of Reactor…"
            rows={3}
            className="w-full bg-surface border border-border rounded-lg px-3 py-2
                       text-xs text-gray-200 placeholder:text-muted font-mono
                       focus:outline-none focus:border-accent/40 resize-none"
          />
          <button
            onClick={sendDirective}
            disabled={!directive.trim() || stopped}
            className="mt-1.5 w-full py-1.5 rounded-lg bg-accent/10 text-accent
                       text-xs font-medium border border-accent/30
                       disabled:opacity-40 hover:bg-accent/20 transition-colors">
            Inject directive →
          </button>
        </div>

        {/* Agent token buffers list */}
        <div className="px-4 py-3 border-b border-border">
          <p className="text-[10px] font-mono text-muted uppercase tracking-wide mb-2">Agents</p>
          <div className="space-y-1">
            {Object.keys(tokenBuf).map(agent => (
              <button key={agent} onClick={() => setActiveAgent(agent)}
                className={`w-full text-left px-2 py-1 rounded text-[11px] font-mono
                  transition-colors flex items-center gap-2
                  ${activeAgent === agent
                    ? 'bg-white/10 text-gray-200'
                    : 'text-muted hover:text-gray-400'}`}>
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  activeAgent === agent ? 'bg-teal' : 'bg-border'
                }`}/>
                {agent.replace(/_/g, '_')}
                <span className="ml-auto text-[9px] text-muted">
                  {tokenBuf[agent]?.length || 0} lines
                </span>
              </button>
            ))}
            {Object.keys(tokenBuf).length === 0 && (
              <p className="text-[10px] text-muted">No active agents</p>
            )}
          </div>
        </div>

        {/* File peek */}
        <div className="flex-1 flex flex-col overflow-hidden px-4 py-3">
          <p className="text-[10px] font-mono text-muted uppercase tracking-wide mb-2">
            File peek {peekFile && <button onClick={() => setPeekFile(null)} className="text-danger ml-1">✕</button>}
          </p>
          {peekFile
            ? <>
                <p className="text-[10px] text-teal font-mono truncate mb-1">
                  {peekFile.split('/').slice(-2).join('/')}
                </p>
                <pre className="flex-1 overflow-auto text-[10px] text-gray-400
                                leading-relaxed font-mono whitespace-pre-wrap">
                  {peekContent || '(empty)'}
                </pre>
              </>
            : <p className="text-[10px] text-muted">
                Click a file in the timeline to preview it.
              </p>
          }
        </div>
      </div>

    </div>
  )
}

// ── Atom ───────────────────────────────────────────────────────────────────────
function CtrlBtn({ onClick, disabled, color, icon, label }) {
  const colors = {
    amber:  'border-amber/40 text-amber  hover:bg-amber/10',
    teal:   'border-teal/40  text-teal   hover:bg-teal/10',
    danger: 'border-danger/40 text-danger hover:bg-danger/10',
  }
  return (
    <button onClick={onClick} disabled={disabled}
      className={`px-2 py-1.5 rounded border text-[11px] font-mono
                  disabled:opacity-30 transition-colors flex items-center gap-1 justify-center
                  ${colors[color] || ''}`}>
      {icon} {label}
    </button>
  )
}
