import React, { useState, useEffect } from 'react'
import { AgentList } from './AgentList'
import { AgentChatView } from './AgentChatView'

export function AgentSidebar({ 
  channels = [], 
  statuses = {}, 
  messages = {}, 
  activeAgent, 
  setActiveAgent, 
  onReply, 
  sending, 
  fetchMessageHistory 
}) {
  const [view, setView] = useState('list') // 'list' | 'chat'

  // If activeAgent changes, switch view to chat
  useEffect(() => {
    if (activeAgent) {
      setView('chat')
      fetchMessageHistory(activeAgent)
    } else {
      setView('list')
    }
  }, [activeAgent, fetchMessageHistory])

  const handleSelectAgent = (agentId) => {
    setActiveAgent(agentId)
  }

  const handleBack = () => {
    setActiveAgent(null)
    setView('list')
  }

  return (
    <div className="w-full h-full flex flex-col bg-[#0c1220] border-l border-slate-800/80 overflow-hidden">
      {view === 'list' ? (
        <AgentList 
          channels={channels} 
          statuses={statuses} 
          onSelectAgent={handleSelectAgent} 
        />
      ) : (
        <AgentChatView 
          agentId={activeAgent} 
          messages={messages[activeAgent] || []} 
          status={statuses[activeAgent] || 'idle'} 
          onBack={handleBack} 
          onReply={onReply}
          sending={sending}
        />
      )}
    </div>
  )
}
