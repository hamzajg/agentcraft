import React from 'react'
import hermesLogo from '../assets/hermes_logo.png'
import { Spinner } from '../ui'

export function HermesTopBar({ 
  connected = false, 
  buildState = null, 
  pendingCount = 0,
  onOpenSettings
}) {
  const isBuilding = buildState && buildState.status === 'building'
  
  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-[#0c1220]/95 backdrop-blur-md border-b border-slate-800/80 flex items-center justify-between px-6">
      {/* Brand Logo & Title */}
      <div className="flex items-center gap-3">
        <img 
          src={hermesLogo} 
          alt="Hermes Logo" 
          className="w-8 h-8 object-contain rounded border border-amber-500/20 shadow shadow-amber-500/10" 
        />
        <div>
          <span 
            className="text-base font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-amber-200 font-serif" 
            style={{ fontFamily: 'var(--font-hermes)' }}
          >
            HERMES
          </span>
          <span className="text-[9px] uppercase tracking-[0.2em] text-slate-500 block leading-none">
            STUDIO
          </span>
        </div>
      </div>

      {/* Build Progress / State Monitor */}
      <div className="flex-1 max-w-md mx-8 hidden sm:flex flex-col gap-1.5">
        {buildState ? (
          <>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                {isBuilding && <Spinner size="sm" />}
                {buildState.phase ? `Phase: ${buildState.phase}` : 'Agent Collaboration'}
              </span>
              <span className="font-mono text-amber-400">{buildState.progress || 0}%</span>
            </div>
            <div className="h-1 bg-slate-900 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-amber-500 to-cyan-400 transition-all duration-500 rounded-full"
                style={{ width: `${buildState.progress || 0}%` }}
              />
            </div>
          </>
        ) : (
          <div className="text-center text-xs text-slate-500 italic">
            Hermes is standing by.
          </div>
        )}
      </div>

      {/* Status Indicators & Action Controls */}
      <div className="flex items-center gap-4 text-xs font-semibold">
        {/* WS Connection Status */}
        <div className="flex items-center gap-2">
          <span 
            className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500 shadow-md shadow-emerald-500/30' : 'bg-slate-500'}`} 
          />
          <span className={connected ? 'text-slate-300' : 'text-slate-500'}>
            {connected ? 'CONNECTED' : 'OFFLINE'}
          </span>
        </div>

        {/* Pending Clarifications Badge */}
        {pendingCount > 0 && (
          <div 
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-400 shadow shadow-amber-500/5 cursor-pointer animate-pulse"
            title={`${pendingCount} replies needed`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span>{pendingCount} REQ</span>
          </div>
        )}

        {/* Global Settings Trigger */}
        <button 
          onClick={onOpenSettings}
          className="p-1.5 rounded border border-slate-800 hover:border-slate-700 bg-slate-900/50 hover:bg-slate-800/50 text-slate-400 hover:text-white transition-all duration-200"
          aria-label="Open settings"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>
    </header>
  )
}
