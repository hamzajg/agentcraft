import React, { useRef, useEffect } from 'react'
import { AgentMessageBubble } from './AgentMessageBubble'
import { AgentReplyBar } from './AgentReplyBar'
import { Avatar, Badge } from '../ui'

export function AgentChatView({ 
  agentId, 
  messages = [], 
  status = 'idle', 
  onBack, 
  onReply, 
  sending 
}) {
  const scrollRef = useRef(null)

  // Find the last pending message (if any)
  const pendingMessage = messages.find(m => m.status === 'pending' && !m.reply)
  const hasPending = !!pendingMessage

  // Scroll to bottom when messages load/change
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendReply = (text) => {
    if (pendingMessage) {
      onReply(pendingMessage.id, text)
    }
  }

  const handleSuggestReply = (text) => {
    if (pendingMessage) {
      onReply(pendingMessage.id, text)
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#0c1220] overflow-hidden">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-900 bg-[#090d16]/30 flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Back to fleet list"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <Avatar name={agentId} size="sm" status={status} />

        <div className="flex-1 min-w-0">
          <h4 className="text-xs font-bold text-slate-100 capitalize font-mono leading-none">
            @{agentId}
          </h4>
          <span className="text-[9px] text-slate-500 uppercase tracking-wider block mt-1">
            Status: {status}
          </span>
        </div>

        <div>
          {hasPending ? (
            <Badge variant="gold" dot={true}>BLOCKED</Badge>
          ) : (
            <Badge variant={status === 'active' || status === 'running' ? 'cyan' : 'default'}>
              {status.toUpperCase()}
            </Badge>
          )}
        </div>
      </div>

      {/* Messages thread */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 hermes-scrollbar">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center text-xs text-slate-500 italic py-12">
            No communication logged on this channel.
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <AgentMessageBubble
                key={msg.id}
                msg={msg}
                isPending={msg.status === 'pending'}
                reply={msg.reply}
                suggestions={msg.suggestions}
                onSuggest={handleSuggestReply}
              />
            ))}
            <div ref={scrollRef} />
          </div>
        )}
      </div>

      {/* Reply input bar */}
      <AgentReplyBar
        onSend={handleSendReply}
        hasPending={hasPending}
        agentId={agentId}
        sending={sending}
      />
    </div>
  )
}
