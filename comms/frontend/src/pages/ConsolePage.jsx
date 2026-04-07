import { useEffect, useRef, useState, useMemo } from 'react'

export function ConsolePage({ logs }) {
  const logsEndRef = useRef(null)
  const [searchText, setSearchText] = useState('')
  const [selectedAgent, setSelectedAgent] = useState('all')

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

  // Get unique agents from logs
  const uniqueAgents = useMemo(() => {
    const agents = new Set(logs.map(log => log.agent_id))
    return Array.from(agents).sort()
  }, [logs])

  // Filter logs based on search and agent filter
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      // Filter by agent
      if (selectedAgent !== 'all' && log.agent_id !== selectedAgent) {
        return false
      }
      
      // Filter by search text
      if (searchText) {
        const search = searchText.toLowerCase()
        return log.message.toLowerCase().includes(search) ||
               log.agent_id.toLowerCase().includes(search)
      }
      
      return true
    })
  }, [logs, selectedAgent, searchText])

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-950">
      <div className="h-11 flex-shrink-0 border-b border-border bg-panel
                      flex items-center px-5 justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium text-gray-200">
            Agent Console Logs
          </span>
          <span className="text-xs text-muted font-mono">
            {filteredLogs.length} / {logs.length} messages
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-400">Live</span>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="flex-shrink-0 border-b border-border bg-panel p-3">
        <div className="flex gap-2">
          {/* Search Input */}
          <div className="flex-1 relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" 
                 viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="7" cy="7" r="5" />
              <path d="M11 11l3.5 3.5" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search logs..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-gray-900 border border-border rounded
                         text-sm text-gray-200 placeholder-gray-600
                         focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Agent Filter */}
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="px-3 py-1.5 bg-gray-900 border border-border rounded
                       text-sm text-gray-200
                       focus:outline-none focus:border-blue-500
                       cursor-pointer"
          >
            <option value="all">All Agents</option>
            {uniqueAgents.map(agent => (
              <option key={agent} value={agent}>
                {agent}
              </option>
            ))}
          </select>

          {/* Clear Filters Button */}
          {(searchText || selectedAgent !== 'all') && (
            <button
              onClick={() => {
                setSearchText('')
                setSelectedAgent('all')
              }}
              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-border rounded
                         text-sm text-gray-300 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 font-mono text-xs bg-gray-950">
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <svg className="w-12 h-12 mb-3 opacity-50" viewBox="0 0 16 16" fill="none" 
                 stroke="currentColor" strokeWidth="1.5">
              <path d="M2 6l4 4-4 4M8 14h6" strokeLinecap="round" strokeLinejoin="round" />
              <rect x="1" y="1" width="14" height="14" rx="1" strokeLinejoin="round" />
            </svg>
            <p className="text-sm">
              {logs.length === 0 ? 'No logs yet' : 'No matching logs'}
            </p>
            <p className="text-xs mt-1">
              {logs.length === 0 
                ? 'Start bootstrap to see agent activity'
                : 'Try adjusting your search or filter'}
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredLogs.map((log, i) => {
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
                  <span className="text-gray-600 flex-shrink-0 select-text cursor-text">
                    {formatTime(log.timestamp)}
                  </span>
                  <span className={`font-semibold flex-shrink-0 select-text cursor-text ${agentColor}`}>
                    [{log.agent_id}]
                  </span>
                  <span className={`
                    break-all select-text
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