import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { FileExplorer } from '../../components/FileExplorer'
import { FileViewer } from '../../components/FileViewer'
import { ActivityPanel } from '../../components/ActivityPanel'
import { FluentEmptyState } from '../../components/FluentEmptyState'
import { HermesChat } from '../chat/HermesChat'
import { AgentSidebar } from '../agents'
import { useHermesData } from '../hooks/useHermesData'
import '../../styles/hermes-design-system.css'

export function HermesWorkspace() {
  // Get central Hermes state
  const {
    connected,
    channels,
    statuses,
    messages,
    busMessages,
    buildState,
    pendingMessages,
    sending,
    fetchMessageHistory,
    sendReply,
    sendMessageToHermes,
  } = useHermesData()

  const location = useLocation()

  // Layout & UI state
  const [selectedFile, setSelectedFile] = useState(null)
  const [activeCenterTab, setActiveCenterTab] = useState('console') // 'console' | 'editor'
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false)
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)
  const [activityMinimized, setActivityMinimized] = useState(true)
  const [activeAgent, setActiveAgent] = useState(null)

  // Listen to navigation state redirects (e.g. from Constellation Map)
  useEffect(() => {
    if (location.state?.selectAgent) {
      setActiveAgent(location.state.selectAgent)
      setRightPanelCollapsed(false)
      // Clear history state to prevent re-activation on refresh
      window.history.replaceState({}, document.title)
    }
  }, [location.state])

  // Sync activeAgent status with incoming notifications
  useEffect(() => {
    // If a new pending request arrives for an agent, we don't force select it, 
    // but we can show visual indicators.
  }, [pendingMessages])


  // Handle selected file from explorer
  const handleFileSelect = useCallback((file) => {
    setSelectedFile(file)
    setActiveCenterTab('editor')
  }, [])

  const handleToggleLeft = () => setLeftPanelCollapsed(p => !p)
  const handleToggleRight = () => setRightPanelCollapsed(p => !p)
  const handleToggleActivity = () => setActivityMinimized(p => !p)

  // Memoized layout classes
  const layout = useMemo(() => ({
    left: leftPanelCollapsed ? 'w-0 border-none opacity-0' : 'w-72 border-r',
    right: rightPanelCollapsed ? 'w-0 border-none opacity-0' : 'w-96 border-l',
    bottom: activityMinimized ? 'h-11' : 'h-48 border-t',
  }), [leftPanelCollapsed, rightPanelCollapsed, activityMinimized])

  return (
    <div className="flex flex-col h-full bg-[#07090f] overflow-hidden select-none">
      {/* Workspace Panel Columns */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Left Column: File Explorer */}
        <div 
          className={`
            ${layout.left} 
            bg-[#0c1220]/50 border-slate-900 transition-all duration-300 flex-shrink-0 flex flex-col overflow-hidden
          `}
        >
          <div className="flex-1 flex flex-col overflow-hidden">
            <FileExplorer 
              selectedFile={selectedFile}
              onFileSelect={handleFileSelect}
              onToggleCollapse={handleToggleLeft}
            />
          </div>
        </div>

        {/* Center Column: Toggleable Console & File Editor */}
        <div className="flex-1 flex flex-col overflow-hidden bg-[#07090f]">
          {/* Center Tabs Control */}
          <div className="h-11 border-b border-slate-900/60 bg-[#090d16]/40 flex items-center justify-between px-4 flex-shrink-0">
            <div className="flex items-center gap-1.5">
              {/* Hermes Console Tab */}
              <button
                onClick={() => setActiveCenterTab('console')}
                className={`
                  px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-2 transition-all
                  ${activeCenterTab === 'console' 
                    ? 'text-amber-400 bg-amber-500/10' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'}
                `}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Hermes Console
              </button>

              {/* File Viewer Tab */}
              {selectedFile && (
                <button
                  onClick={() => setActiveCenterTab('editor')}
                  className={`
                    px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-2 transition-all
                    ${activeCenterTab === 'editor' 
                      ? 'text-cyan-400 bg-cyan-500/10' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'}
                  `}
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                  Viewer: {selectedFile.split('/').pop()}
                </button>
              )}
            </div>

            {/* Toggle Left/Right expand collapse buttons */}
            <div className="flex items-center gap-1">
              <button 
                onClick={handleToggleLeft}
                className={`p-1.5 rounded hover:bg-slate-800/50 text-slate-500 hover:text-slate-300 transition-all ${leftPanelCollapsed ? 'text-amber-400 bg-amber-500/5' : ''}`}
                title={leftPanelCollapsed ? "Expand explorer" : "Collapse explorer"}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h10M4 18h16" />
                </svg>
              </button>
              <button 
                onClick={handleToggleRight}
                className={`p-1.5 rounded hover:bg-slate-800/50 text-slate-500 hover:text-slate-300 transition-all ${rightPanelCollapsed ? 'text-amber-400 bg-amber-500/5' : ''}`}
                title={rightPanelCollapsed ? "Expand agents" : "Collapse agents"}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857" />
                </svg>
              </button>
            </div>
          </div>

          {/* Render Active Tab */}
          <div className="flex-1 overflow-hidden relative">
            {activeCenterTab === 'console' ? (
              <HermesChat
                messages={messages['hermes'] || []}
                onSendMessage={sendMessageToHermes}
                sending={sending}
              />
            ) : selectedFile ? (
              <FileViewer 
                file={selectedFile}
                onClose={() => setActiveCenterTab('console')}
              />
            ) : (
              <FluentEmptyState />
            )}
          </div>
        </div>

        {/* Right Column: Decomposed Agent Sidebar */}
        <div 
          className={`
            ${layout.right} 
            bg-[#0c1220]/50 border-slate-900 transition-all duration-300 flex-shrink-0 flex flex-col overflow-hidden
          `}
        >
          <AgentSidebar
            channels={channels}
            statuses={statuses}
            messages={messages}
            activeAgent={activeAgent}
            setActiveAgent={setActiveAgent}
            onReply={sendReply}
            sending={sending}
            fetchMessageHistory={fetchMessageHistory}
          />
        </div>
      </div>

      {/* Bottom Row: Activity Feed Panel */}
      <div 
        className={`
          ${layout.bottom} 
          bg-[#0c1220]/80 border-slate-900/60 transition-all duration-300 flex-shrink-0 flex flex-col overflow-hidden z-30
        `}
      >
        <ActivityPanel 
          minimized={activityMinimized}
          onToggleMinimize={handleToggleActivity}
        />
      </div>
    </div>
  )
}
