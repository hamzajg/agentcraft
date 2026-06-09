import React, { useState } from 'react'
import { AgentCard } from './AgentCard'

export function AgentList({ channels = [], statuses = {}, onSelectAgent }) {
  const [search, setSearch] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState({
    blocked: false,
    running: false,
    idle: false,
  })

  // Filter channels by search query
  const filteredChannels = channels.filter(ch => 
    ch.agent_id.toLowerCase().includes(search.toLowerCase())
  )

  // Exclude hermes from the standard list since Hermes is in the main chat console
  const nonHermesChannels = filteredChannels.filter(ch => ch.agent_id !== 'hermes')

  // Group agents by status
  const groups = {
    blocked: [],
    running: [],
    idle: [],
  }

  nonHermesChannels.forEach(ch => {
    const status = statuses[ch.agent_id] || 'idle'
    if (status === 'blocked' || status === 'pending') {
      groups.blocked.push(ch)
    } else if (status === 'active' || status === 'running') {
      groups.running.push(ch)
    } else {
      groups.idle.push(ch)
    }
  })

  const toggleGroup = (groupName) => {
    setCollapsedGroups(prev => ({
      ...prev,
      [groupName]: !prev[groupName]
    }))
  }

  const renderGroupSection = (groupName, label, list, colorClass) => {
    if (list.length === 0) return null
    const isCollapsed = collapsedGroups[groupName]

    return (
      <div className="space-y-2.5">
        <button
          onClick={() => toggleGroup(groupName)}
          className="w-full flex items-center justify-between text-[11px] font-bold text-slate-500 uppercase tracking-wider py-1 hover:text-slate-300 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${colorClass}`} />
            {label} ({list.length})
          </span>
          <span>{isCollapsed ? 'Expand' : 'Collapse'}</span>
        </button>
        
        {!isCollapsed && (
          <div className="flex flex-col gap-2.5">
            {list.map(ch => (
              <AgentCard
                key={ch.agent_id}
                channel={ch}
                status={statuses[ch.agent_id] || 'idle'}
                onClick={() => onSelectAgent(ch.agent_id)}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-[#0c1220] overflow-hidden">
      {/* Search Header */}
      <div className="p-4 border-b border-slate-900 bg-[#090d16]/30 flex flex-col gap-3">
        <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
          <svg className="w-4 h-4 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          Specialist Fleet
        </h3>
        <div className="relative">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search agents..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg py-1.5 pl-8 pr-3 text-xs text-slate-100 placeholder-slate-500 outline-none focus:border-amber-500/50 focus:shadow focus:shadow-amber-500/5 transition-all"
          />
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* Roster List Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 hermes-scrollbar">
        {nonHermesChannels.length === 0 ? (
          <div className="text-center text-xs text-slate-500 py-12 italic">
            No agents found.
          </div>
        ) : (
          <>
            {renderGroupSection('blocked', 'Blocked', groups.blocked, 'bg-amber-400 animate-pulse')}
            {renderGroupSection('running', 'Active', groups.running, 'bg-emerald-400')}
            {renderGroupSection('idle', 'Idle', groups.idle, 'bg-slate-500')}
          </>
        )}
      </div>
    </div>
  )
}
