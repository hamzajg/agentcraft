import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { FileExplorer, FileViewer, ActivityPanel, FluentEmptyState, AgentPanelRedesigned } from './'
import { useWebSocket } from '../hooks/useWebSocket'
import { api } from '../lib/api'
import '../styles/design-system.css'

/* ─────────────────────────────────────────
   Modern Workspace Layout v3.0
   Architecture:
   • Three-panel responsive design
   • Smart state management
   • Optimized component organization
   • Enhanced visual hierarchy
   • Seamless transitions
   
   Layout Structure:
   Left: File Explorer (collapsible, 280px)
   Center: Content Area (file viewer/empty state)
   Right: Agent Panel (collapsible, 380px)
   Bottom: Activity Feed (minimizable)
   ───────────────────────────────────────── */

export function WorkspaceLayout() {
  // Core state management
  const [selectedFile, setSelectedFile] = useState(null)
  const [showFileViewer, setShowFileViewer] = useState(false)
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false)
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)
  const [activityMinimized, setActivityMinimized] = useState(true)

  // Agent build overlay state
  const [agentBuildReport, setAgentBuildReport] = useState(null)
  const [showBuildPanel, setShowBuildPanel] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState(null)

  // WebSocket state
  const [channels, setChannels] = useState([])
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState({})
  const [activeAgent, setActiveAgent] = useState(null)
  const [sending, setSending] = useState(false)
  const [busMessages, setBusMessages] = useState([])

  // WebSocket integration
  useWebSocket((data) => {
    // Handle WebSocket messages here
    console.log('WebSocket message:', data)
  })

  // Reply handler
  const onReply = useCallback((message) => {
    console.log('Reply:', message)
    // Handle reply logic here
  }, [])

  // Agent build report polling
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
            setShowBuildPanel(true)
          }
          return
        }
      } catch (e) { /* ignore polling errors */ }
      
      if (attempts >= maxAttempts) {
        if (!cancelled) setAgentBuildReport(null)
        return
      }
      
      if (!cancelled) setTimeout(poll, 2000)
    }
    
    poll()
    
    return () => { cancelled = true }
  }, [])

  // Memoized layout calculations
  const layoutClasses = useMemo(() => ({
    leftPanel: leftPanelCollapsed ? 'w-12' : 'w-[280px]',
    centerPanel: 'flex-1 min-w-0',
    rightPanel: rightPanelCollapsed ? 'w-16' : 'w-[380px]',
    activityPanel: activityMinimized ? 'h-12' : 'h-32'
  }), [leftPanelCollapsed, rightPanelCollapsed, activityMinimized])

  // Event handlers
  const handleFileSelect = useCallback((file) => {
    setSelectedFile(file)
    setShowFileViewer(true)
  }, [])

  const handleToggleLeftPanel = useCallback(() => {
    setLeftPanelCollapsed(prev => !prev)
  }, [])

  const handleToggleRightPanel = useCallback(() => {
    setRightPanelCollapsed(prev => !prev)
  }, [])

  const handleToggleActivity = useCallback(() => {
    setActivityMinimized(prev => !prev)
  }, [])

  const handleCloseBuildPanel = useCallback(() => {
    setShowBuildPanel(false)
    setSelectedAgent(null)
  }, [])

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-primary)' }}>
      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel - File Explorer */}
        <div 
          className={`
            ${layoutClasses.leftPanel}
            border-r transition-all duration-300
            flex-shrink-0 overflow-hidden
          `}
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          {!leftPanelCollapsed ? (
            <FileExplorer 
              selectedFile={selectedFile}
              onFileSelect={handleFileSelect}
              onToggleCollapse={handleToggleLeftPanel}
            />
          ) : (
            <CollapsedFileExplorer onExpand={handleToggleLeftPanel} />
          )}
        </div>

        {/* Center Panel - Content Area */}
        <div className={layoutClasses.centerPanel}>
          {showFileViewer && selectedFile ? (
            <FileViewer 
              file={selectedFile}
              onClose={() => setShowFileViewer(false)}
            />
          ) : (
            <FluentEmptyState />
          )}
        </div>

        {/* Right Panel - Agent Chat */}
        <div 
          className={`
            ${layoutClasses.rightPanel}
            border-l transition-all duration-300
            flex-shrink-0 overflow-hidden
          `}
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <AgentPanelRedesigned
            channels={channels}
            statuses={statuses}
            messages={messages}
            activeAgent={activeAgent}
            setActiveAgent={setActiveAgent}
            sending={sending}
            onReply={onReply}
            busMessages={busMessages}
            isCollapsed={rightPanelCollapsed}
            setIsCollapsed={setRightPanelCollapsed}
          />
        </div>
      </div>

      {/* Bottom Panel - Activity Feed */}
      <div 
        className={`
          ${layoutClasses.activityPanel}
          border-t transition-all duration-300
          overflow-hidden
        `}
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <ActivityPanel 
          minimized={activityMinimized}
          onToggleMinimize={handleToggleActivity}
        />
      </div>

      {/* Agent Build Overlay */}
      {showBuildPanel && agentBuildReport && (
        <AgentBuildOverlay
          agents={agentBuildReport}
          selectedAgent={selectedAgent}
          onSelectAgent={setSelectedAgent}
          onClose={handleCloseBuildPanel}
        />
      )}
    </div>
  )
}

/* ─────────────────────────────────────────
   Collapsed File Explorer Component
   Minimal state when file explorer is collapsed
   ───────────────────────────────────────── */

function CollapsedFileExplorer({ onExpand }) {
  return (
    <div className="flex flex-col items-center py-4 gap-3 h-full">
      <button
        onClick={onExpand}
        className="p-2 rounded-lg transition-all duration-200 hover:scale-105"
        style={{ 
          background: 'var(--bg-tertiary)', 
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-secondary)'
        }}
        title="Expand File Explorer"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 12h18m-9-9l9 9-9 9" />
        </svg>
      </button>
      
      <div className="flex-1 flex flex-col items-center gap-2">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'var(--accent-primary)' }}
        >
          <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
            <path d="M8 21v-4a2 2 0 012-2h4a2 2 0 012 2v4" />
          </svg>
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────
   Agent Build Overlay Component
   Slides in from right when agent build report is available
   ───────────────────────────────────────── */

function AgentBuildOverlay({ agents, selectedAgent, onSelectAgent, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-4xl mx-4 rounded-xl shadow-2xl"
        style={{ 
          background: 'var(--bg-secondary)', 
          borderColor: 'var(--border-subtle)',
          borderWidth: '1px'
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              Agent Build Report
            </h2>
            <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
              Review agent build status and details
            </p>
          </div>
          
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors"
            style={{ color: 'var(--text-tertiary)' }}
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-96 overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(agents).map(([agentId, data]) => (
              <div
                key={agentId}
                className="p-4 rounded-lg border cursor-pointer transition-all duration-200 hover:scale-105"
                style={{
                  background: selectedAgent === agentId ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                  borderColor: 'var(--border-subtle)',
                  color: selectedAgent === agentId ? 'var(--bg-primary)' : 'var(--text-primary)'
                }}
                onClick={() => onSelectAgent(agentId)}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{agentId}</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    data.status === 'success' ? 'bg-green-100 text-green-800' :
                    data.status === 'error' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {data.status}
                  </span>
                </div>
                <div className="text-sm opacity-75">
                  {data.message || 'No message available'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
