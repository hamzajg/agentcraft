import { useEffect, useRef } from 'react'

export function ConsolePage({ logs }) {
  const logsEndRef = useRef(null)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Color map for different agents
  const agentColors = {
    supervisor: 'text-purple-400',
    architect: 'text-blue-400',
    spec: 'text-green-400',
    planner: 'text-yellow-400',
    backend_dev: 'text-orange-400',
    test_dev: 'text-pink-400',
    reviewer: 'text-red-400',
    integration_test: 'text-indigo-400',
    cicd: 'text-teal-400',
    config_agent: 'text-cyan-400',
    docs_agent: 'text-emerald-400',
  }

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-950">
      <div className="h-11 flex-shrink-0 border-b border-border bg-panel
                      flex items-center px-5 justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium text-gray-200">
            Agent Console Logs
          </span>
          <span className="text-xs text-muted font-mono">
            {logs.length} messages
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-400">Live</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 font-mono text-xs bg-gray-950">
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <svg className="w-12 h-12 mb-3 opacity-50" viewBox="0 0 16 16" fill="none" 
                 stroke="currentColor" strokeWidth="1.5">
              <path d="M2 6l4 4-4 4M8 14h6" strokeLinecap="round" strokeLinejoin="round" />
              <rect x="1" y="1" width="14" height="14" rx="1" strokeLinejoin="round" />
            </svg>
            <p className="text-sm">No logs yet</p>
            <p className="text-xs mt-1">Start bootstrap to see agent activity</p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {logs.map((log, i) => {
              const agentColor = agentColors[log.agent_id] || 'text-gray-400'
              const isError = log.message.includes('ERROR') || log.message.includes('FAILED')
              const isWarning = log.message.includes('WARNING') || log.message.includes('WARN')
              
              return (
                <div 
                  key={i} 
                  className={`
                    flex gap-3 py-1 px-2 rounded hover:bg-gray-900/50 transition-colors
                    ${isError ? 'bg-red-950/20' : isWarning ? 'bg-yellow-950/20' : ''}
                  `}
                >
                  <span className="text-gray-600 flex-shrink-0 select-none">
                    {formatTime(log.timestamp)}
                  </span>
                  <span className={`font-semibold flex-shrink-0 select-none ${agentColor}`}>
                    [{log.agent_id}]
                  </span>
                  <span className={`
                    break-all
                    ${isError ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-gray-300'}
                  `}>
                    {log.message}
                  </span>
                </div>
              )
            })}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}