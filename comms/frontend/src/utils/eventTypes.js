export const EVENT_TYPES = {
  // Agent events
  agent_query: { color: 'var(--warning)', label: 'QUERY' },
  agent_reply: { color: 'var(--success)', label: 'REPLY' },
  agent_delegate: { color: 'var(--accent-primary)', label: 'DELEGATE' },
  agent_context: { color: 'var(--info)', label: 'CONTEXT' },
  agent_broadcast: { color: 'var(--text-secondary)', label: 'BROADCAST' },
  agent_status: { color: 'var(--text-tertiary)', label: 'STATUS' },
  
  // Build events
  build_started: { color: 'var(--success)', label: 'BUILD' },
  build_done: { color: 'var(--success)', label: 'BUILD' },
  build_error: { color: 'var(--danger)', label: 'BUILD' },
  phase_started: { color: 'var(--accent-primary)', label: 'PHASE' },
  phase_done: { color: 'var(--accent-primary)', label: 'PHASE' },
  iter_started: { color: 'var(--info)', label: 'ITER' },
  iter_done: { color: 'var(--info)', label: 'ITER' },
  task_started: { color: 'var(--accent-primary)', label: 'TASK' },
  task_done: { color: 'var(--success)', label: 'TASK' },
  
  // System events
  paused: { color: 'var(--warning)', label: 'PAUSED' },
  resumed: { color: 'var(--success)', label: 'RESUMED' },
  stopped: { color: 'var(--danger)', label: 'STOPPED' },
  error: { color: 'var(--danger)', label: 'ERROR' },
  
  // File events
  file_written: { color: 'var(--success)', label: 'FILE' },
  
  // Review events
  reviewer_verdict: { color: 'var(--warning)', label: 'REVIEW' },
  approval_gate: { color: 'var(--warning)', label: 'APPROVAL' },
  
  // Communication
  clarification: { color: 'var(--warning)', label: 'CLARIFY' },
  directive_injected: { color: 'var(--accent-primary)', label: 'DIRECTIVE' },
  
  // Log
  log: { color: 'var(--text-tertiary)', label: 'LOG' },
}

export function getEventTypeInfo(type) {
  return EVENT_TYPES[type] || { 
    color: 'var(--text-secondary)', 
    label: type?.toUpperCase().replace(/_/g, ' ') || 'EVENT' 
  }
}

export function isAgentEvent(type) {
  return type?.startsWith('agent_')
}

export function isBuildEvent(type) {
  return ['build_started', 'build_done', 'build_error', 'phase_started', 'phase_done', 
          'iter_started', 'iter_done', 'task_started', 'task_done'].includes(type)
}
