import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { HermesTopBar } from './HermesTopBar'
import { HermesSidebar } from './HermesSidebar'
import { useHermesData } from '../hooks/useHermesData'
import '../styles/hermes-design-system.css'

export function HermesShell() {
  const { 
    connected, 
    buildState, 
    pendingMessages, 
    stats 
  } = useHermesData()

  const [showSettings, setShowSettings] = useState(false)

  const handleOpenSettings = () => {
    setShowSettings(prev => !prev)
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#07090f] text-slate-100 font-sans">
      {/* Top Bar Navigation */}
      <HermesTopBar 
        connected={connected} 
        buildState={buildState} 
        pendingCount={pendingMessages.length}
        onOpenSettings={handleOpenSettings}
      />

      {/* Main Container */}
      <div className="flex flex-1 pt-16 pl-16 relative overflow-hidden">
        {/* Sidebar Navigation */}
        <HermesSidebar stats={stats} />

        {/* Content Outlet for routes */}
        <main className="flex-1 h-full overflow-hidden relative">
          <Outlet />
        </main>
      </div>

      {/* Settings Modal (Overlay) */}
      {showSettings && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0c1220] border border-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl relative">
            <button 
              onClick={() => setShowSettings(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <h3 className="text-lg font-bold text-amber-400 font-serif mb-4" style={{ fontFamily: 'var(--font-hermes)' }}>
              Hermes Studio Settings
            </h3>
            
            <div className="space-y-4 text-sm text-slate-300">
              <div className="p-3 bg-slate-900/60 rounded border border-slate-800">
                <span className="text-xs text-slate-500 uppercase font-bold tracking-wider block mb-1">
                  Active Endpoint
                </span>
                <span className="font-mono text-cyan-400">http://localhost:7000/api</span>
              </div>
              <div className="p-3 bg-slate-900/60 rounded border border-slate-800">
                <span className="text-xs text-slate-500 uppercase font-bold tracking-wider block mb-1">
                  Event Bus Subscriptions
                </span>
                <span className="text-slate-300">All 11 agents monitored over shared events channel</span>
              </div>
              <div className="p-3 bg-slate-900/60 rounded border border-slate-800">
                <span className="text-xs text-slate-500 uppercase font-bold tracking-wider block mb-1">
                  Design Accent
                </span>
                <span className="text-amber-400">Hermes Gold (#FFB830)</span>
              </div>
            </div>
            
            <div className="mt-6 flex justify-end">
              <button 
                onClick={() => setShowSettings(false)}
                className="px-4 py-2 rounded bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs transition-colors"
              >
                Close Settings
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
