import { useState, useMemo, useRef, useEffect } from 'react'
import { Badge, Avatar, StatusDot } from './ui'

export function AgentPanel({ channels, statuses, messages, activeAgent, setActiveAgent, sending, onReply }) {
  const [replyText, setReplyText] = useState('')
  const [view, setView] = useState('list') // 'list' or 'chat'
  const messagesEndRef = useRef(null)

  const channelMessages = useMemo(
    () => (activeAgent ? messages[activeAgent] ?? [] : []),
    [activeAgent, messages]
  )

  const pendingMessage = channelMessages.find(m => m.status === 'pending')
  const selectedChannel = channels.find(c => c.agent_id === activeAgent)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [channelMessages])

  const handleSend = async () => {
    if (!pendingMessage || !replyText.trim()) return
    await onReply(pendingMessage.id, replyText)
    setReplyText('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleAgentClick = (agentId) => {
    setActiveAgent(agentId)
    setView('chat')
  }

  const handleBackToList = () => {
    setView('list')
  }

  const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="h-full flex flex-col bg-slate-950">
      {view === 'list' ? (
        <>
          {/* Header */}
          <div className="px-4 py-3 border-b border-slate-800">
            <h2 className="text-sm font-semibold text-slate-200">Agents</h2>
            <p className="text-xs text-slate-500 mt-0.5">{channels.length} connected</p>
          </div>

          {/* Agent list */}
          <div className="flex-1 overflow-y-auto">
            {channels.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 p-4">
                <AgentsIcon className="w-10 h-10 mb-3 opacity-50" />
                <p className="text-sm">No agents connected</p>
                <p className="text-xs mt-1">Agents will appear here when they connect</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/50">
                {channels.map((channel) => {
                  const status = statuses[channel.agent_id] || 'idle'
                  const agentMessages = messages[channel.agent_id] || []
                  const hasPending = agentMessages.some(m => m.status === 'pending')

                  return (
                    <button
                      key={channel.agent_id}
                      onClick={() => handleAgentClick(channel.agent_id)}
                      className={`w-full flex items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-slate-800/30 ${
                        activeAgent === channel.agent_id ? 'bg-accent/10' : ''
                      }`}
                    >
                      <Avatar name={channel.agent_id} size="lg" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-slate-200 truncate">
                            {channel.agent_label || channel.agent_id}
                          </p>
                          <StatusDot status={status} pulse={status === 'running'} />
                        </div>
                        <p className="text-xs text-slate-500 font-mono">{channel.agent_id}</p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <Badge variant={status === 'running' ? 'success' : 'muted'}>
                          {status}
                        </Badge>
                        {hasPending && (
                          <span className="w-2 h-2 rounded-full bg-amber animate-pulse" />
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </>
      ) : (
        <>
          {/* Chat view header */}
          <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-3">
            <button
              onClick={handleBackToList}
              className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <BackIcon className="w-4 h-4 text-slate-400" />
            </button>
            {selectedChannel && (
              <>
                <Avatar name={activeAgent} size="sm" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">
                    {selectedChannel.agent_label || selectedChannel.agent_id}
                  </p>
                  <p className="text-xs text-slate-500">
                    {statuses[activeAgent] || 'idle'}
                  </p>
                </div>
                <StatusDot status={statuses[activeAgent] || 'idle'} pulse={statuses[activeAgent] === 'running'} />
              </>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {channelMessages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <ChatIcon className="w-10 h-10 mb-3 opacity-50" />
                <p className="text-sm">No messages yet</p>
                <p className="text-xs mt-1">Start a conversation with {activeAgent}</p>
              </div>
            ) : (
              <>
                {channelMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`rounded-xl border p-4 ${
                      msg.status === 'pending'
                        ? 'border-amber/30 bg-amber/5'
                        : msg.status === 'replied'
                        ? 'border-teal/30 bg-teal/5'
                        : 'border-slate-800 bg-slate-900/50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-slate-400">
                        {msg.agent_label || msg.agent_id}
                      </span>
                      <div className="flex items-center gap-2">
                        {msg.status === 'pending' && (
                          <Badge variant="warning" className="text-xs">Pending</Badge>
                        )}
                        {msg.status === 'replied' && (
                          <Badge variant="success" className="text-xs">Resolved</Badge>
                        )}
                        <span className="text-xs text-slate-500">{formatTime(msg.created_at)}</span>
                      </div>
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                      {msg.question || msg.reply || 'No content'}
                    </p>
                    {msg.reply && (
                      <div className="mt-3 pt-3 border-t border-slate-700">
                        <p className="text-xs text-teal font-medium mb-1">Your response:</p>
                        <p className="text-sm text-slate-300">{msg.reply}</p>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Reply composer */}
          <div className="border-t border-slate-800 p-4">
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={pendingMessage ? 'Type your reply...' : 'No pending requests'}
              disabled={!pendingMessage || sending}
              rows={3}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent/50 resize-none disabled:opacity-50"
            />
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-slate-500">
                {pendingMessage ? `Replying to ${activeAgent}` : 'Idle'}
              </span>
              <button
                onClick={handleSend}
                disabled={!pendingMessage || sending || !replyText.trim()}
                className="px-4 py-2 bg-accent hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                {sending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <SendIcon className="w-4 h-4" />
                    Send
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function BackIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  )
}

function SendIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function ChatIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function AgentsIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}
