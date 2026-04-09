import { useState } from 'react'
import { FileExplorer } from './FileExplorer'
import { FileViewer } from './FileViewer'
import { AgentPanel } from './AgentPanel'
import { ActivityPanel } from './ActivityPanel'
import { Header } from './layout'

export function WorkspaceLayout({
  channels,
  statuses,
  messages,
  events,
  activeAgent,
  setActiveAgent,
  connected,
  pendingCount,
  sending,
  onReply,
  onRefresh,
}) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [showFileViewer, setShowFileViewer] = useState(true)
  const [activityMinimized, setActivityMinimized] = useState(true) // Hidden by default

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
      {/* Header */}
      <Header
        connected={connected}
        pendingCount={pendingCount}
        agentCount={channels.length}
        onLogoClick={() => {}}
      />

      {/* Main content - 2 panes (no right panel, activity is floating) */}
      <div className="flex-1 flex overflow-hidden pb-20">
        {/* Left pane - File Explorer */}
        <div className="w-72 flex-shrink-0 border-r border-slate-800 overflow-hidden">
          <FileExplorer onFileSelect={handleFileSelect} />
        </div>

        {/* Center pane - File Viewer */}
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

        {/* Right pane - Agent Panel */}
        <div className="w-80 flex-shrink-0 overflow-hidden border-l border-slate-800">
          <AgentPanel
            channels={channels}
            statuses={statuses}
            messages={messages}
            activeAgent={activeAgent}
            setActiveAgent={setActiveAgent}
            sending={sending}
            onReply={onReply}
          />
        </div>
      </div>

      {/* Floating Activity Panel */}
      <ActivityPanel 
        events={events} 
        onMinimize={setActivityMinimized}
      />
    </div>
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
