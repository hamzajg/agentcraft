import { useState, useMemo, useRef, useEffect } from 'react'
import { Badge, Avatar } from './ui'

export function AgentPanel({ channels, statuses, messages, events, activeAgent, setActiveAgent, sending, onReply }) {
  const [showChat, setShowChat] = useState(false)
  const [replyText, setReplyText] = useState('')
  const [localReplies, setLocalReplies] = useState({}) // msgId -> reply text for optimistic updates
  const [showArchived, setShowArchived] = useState(false)
  const messagesEndRef = useRef(null)

  const selectedChannel = channels.find(c => c.agent_id === activeAgent)

  // Sort ALL messages by created_at ascending (oldest first)
  const allMessages = useMemo(() => {
    if (!activeAgent) return []
    const msgs = messages[activeAgent] ?? []
    return [...msgs].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  }, [activeAgent, messages])

  // Find the most recent pending message
  const currentPending = useMemo(() => {
    const pending = allMessages.filter(m => m.status === 'pending')
    if (pending.length === 0) return null
    // Return the one with latest created_at
    return pending.reduce((latest, m) => 
      new Date(m.created_at) > new Date(latest.created_at) ? m : latest
    )
  }, [allMessages])

  // Find the index of currentPending in allMessages
  const currentPendingIdx = useMemo(() => {
    if (!currentPending) return -1
    return allMessages.findIndex(m => m.id === currentPending.id)
  }, [allMessages, currentPending])

  // Show messages from currentPending onwards, or last 5 if no pending
  const visibleMessages = useMemo(() => {
    if (allMessages.length === 0) return []
    if (currentPendingIdx >= 0) {
      return allMessages.slice(currentPendingIdx)
    }
    return allMessages.slice(-5) // Last 5 if no pending
  }, [allMessages, currentPendingIdx])

  // Auto-scroll
  useEffect(() => {
    if (visibleMessages.length > 0) {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      }, 100)
    }
  }, [visibleMessages.length, currentPending?.id])

  const handleAgentClick = (agentId) => {
    setActiveAgent(agentId)
    setShowChat(true)
    setLocalReplies({})
    setReplyText('')
  }

  const handleBack = () => {
    setShowChat(false)
    setLocalReplies({})
    setReplyText('')
  }

  const handleSend = async () => {
    if (!currentPending || !replyText.trim()) return
    
    const msgId = currentPending.id
    const text = replyText
    
    // Optimistic update
    setLocalReplies(prev => ({ ...prev, [msgId]: text }))
    setReplyText('')
    
    try {
      await onReply(msgId, text)
    } catch (err) {
      console.error('Send failed:', err)
      // Rollback on error
      setLocalReplies(prev => {
        const next = { ...prev }
        delete next[msgId]
        return next
      })
    }
  }

  const handleSuggestionClick = async (suggestion, msgId) => {
    if (!msgId || sending) return
    
    // Optimistic update
    setLocalReplies(prev => ({ ...prev, [msgId]: suggestion }))
    
    try {
      await onReply(msgId, suggestion)
    } catch (err) {
      console.error('Send failed:', err)
      setLocalReplies(prev => {
        const next = { ...prev }
        delete next[msgId]
        return next
      })
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="h-full flex flex-col bg-slate-950">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        {!showChat ? (
          <>
            <h2 className="text-sm font-semibold text-slate-200">Agents</h2>
            <div className="flex items-center gap-2">
              {currentPending && (
                <Badge variant="warning" className="animate-pulse text-xs">Needs input</Badge>
              )}
              <span className="text-xs text-slate-500">{channels.length}</span>
            </div>
          </>
        ) : (
          <>
            <button
              onClick={handleBack}
              className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 px-2 py-1 rounded-lg hover:bg-slate-800 transition-colors mr-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M15 18l-6-6 6-6" />
              </svg>
              <span>Back</span>
            </button>
            {selectedChannel && (
              <>
                <Avatar name={activeAgent} size="sm" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">
                    {selectedChannel.agent_label || activeAgent}
                  </p>
                  <p className="text-xs text-slate-500 capitalize">
                    {statuses[activeAgent] || 'idle'}
                  </p>
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Agent List */}
      {!showChat && (
        <div className="flex-1 overflow-y-auto">
          {channels.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 p-4">
              <svg className="w-12 h-12 mb-4 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
              <p className="text-sm">No agents connected</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/50">
              {channels.map((channel) => {
                const status = statuses[channel.agent_id] || 'idle'
                const agentMessages = messages[channel.agent_id] || []
                const hasPending = agentMessages.some(m => m.status === 'pending')
                const lastMsg = [...agentMessages].sort((a, b) => 
                  new Date(b.created_at) - new Date(a.created_at)
                )[0]

                return (
                  <button
                    key={channel.agent_id}
                    onClick={() => handleAgentClick(channel.agent_id)}
                    className={`w-full flex items-center gap-3 px-4 py-3.5 text-left transition-colors ${
                      activeAgent === channel.agent_id ? 'bg-accent/10 border-l-2 border-accent' : 'hover:bg-slate-800/30'
                    }`}
                  >
                    <div className="relative flex-shrink-0">
                      <Avatar name={channel.agent_id} size="md" />
                      <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-slate-950 ${
                        status === 'running' ? 'bg-teal' : status === 'idle' ? 'bg-slate-500' : 'bg-amber'
                      }`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-slate-200 truncate">
                          {channel.agent_label || channel.agent_id}
                        </p>
                        {hasPending && (
                          <span className="w-2 h-2 rounded-full bg-amber animate-pulse flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-slate-500 capitalize mt-0.5">{status}</p>
                      {lastMsg && (
                        <p className="text-xs text-slate-600 truncate mt-1">
                          {lastMsg.question?.slice(0, 50) || lastMsg.reply?.slice(0, 50) || 'No messages'}
                        </p>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Chat View */}
      {showChat && activeAgent && (
        <>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {/* Visible messages */}
            {visibleMessages.map((msg) => {
              const isCurrentPending = msg.id === currentPending?.id
              const userReply = localReplies[msg.id] || msg.reply
              
              return (
                <div key={msg.id} className="space-y-2">
                  {/* Agent message */}
                  <div className={`rounded-xl border p-3 ${
                    isCurrentPending && !userReply
                      ? 'border-amber/30 bg-amber/5' 
                      : 'border-slate-800 bg-slate-900/30'
                  }`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <Avatar name={msg.agent_id} size="sm" />
                        <span className="text-xs font-medium text-slate-300">@{msg.agent_id}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isCurrentPending && !userReply && (
                          <span className="flex items-center gap-1 text-xs text-amber">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
                            Awaiting reply
                          </span>
                        )}
                        <span className="text-xs text-slate-500">{formatTime(msg.created_at)}</span>
                      </div>
                    </div>
                    
                    <p className="text-sm text-slate-200 whitespace-pre-wrap">
                      {msg.question}
                    </p>

                    {/* Suggestions - only for current pending without reply */}
                    {msg.suggestions?.length > 0 && isCurrentPending && !userReply && (
                      <div className="border-t border-slate-700/50 pt-2 mt-2">
                        <p className="text-xs text-slate-500 mb-1.5">Quick replies:</p>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.suggestions.map((s, i) => (
                            <button
                              key={i}
                              onClick={() => handleSuggestionClick(s, msg.id)}
                              disabled={sending}
                              className="text-xs px-2.5 py-1 rounded-lg bg-slate-800/50 border border-slate-700 text-slate-300 hover:bg-accent hover:border-accent/30 hover:text-white transition-colors disabled:opacity-50"
                            >
                              {s.length > 40 ? s.slice(0, 40) + '...' : s}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* User reply */}
                  {userReply && (
                    <div className="rounded-xl border border-teal/30 bg-teal/5 p-3 ml-6">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <div className="w-4 h-4 rounded-full bg-teal/20 flex items-center justify-center">
                          <svg className="w-2.5 h-2.5 text-teal" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                            <circle cx="12" cy="7" r="4" />
                          </svg>
                        </div>
                        <span className="text-xs font-medium text-teal">You</span>
                        <span className="text-xs text-slate-500 ml-auto">{formatTime(msg.replied_at || msg.created_at)}</span>
                      </div>
                      <p className="text-sm text-slate-200 whitespace-pre-wrap">{userReply}</p>
                    </div>
                  )}
                </div>
              )
            })}
            
            {visibleMessages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <svg className="w-12 h-12 mb-4 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <p className="text-sm">No messages yet</p>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Reply input */}
          <div className="border-t border-slate-800 p-3 space-y-2">
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={currentPending ? 'Type your reply...' : 'No pending requests'}
              disabled={!currentPending || sending}
              rows={2}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent/50 resize-none disabled:opacity-50"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">
                {currentPending ? `Replying to @${activeAgent}` : 'Idle'}
              </span>
              <button
                onClick={handleSend}
                disabled={!currentPending || !replyText.trim() || sending}
                className="px-4 py-1.5 rounded-lg bg-accent hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
              >
                Send
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
  if (seconds < 5) return 'Just now'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h`
}
