import { useState, useMemo } from 'react'
import { Card, Badge, Button, Input } from '../components/ui'
import { AgentCard } from '../components/AgentCard'
import { MessageThread } from '../components/MessageThread'

export function Chat({ channels, statuses, messages, activeAgent, setActiveAgent, onNavigate, sending, setSending, onRefresh }) {
  const [replyText, setReplyText] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredChannels = useMemo(() => {
    if (!searchQuery) return channels
    const q = searchQuery.toLowerCase()
    return channels.filter(ch => 
      ch.agent_id.toLowerCase().includes(q) ||
      (ch.agent_label || '').toLowerCase().includes(q)
    )
  }, [channels, searchQuery])

  const channelMessages = useMemo(
    () => (activeAgent ? messages[activeAgent] ?? [] : []),
    [activeAgent, messages]
  )

  const getPendingCount = (agentId) => {
    const msgs = messages[agentId] ?? []
    return msgs.filter(m => m.status === 'pending').length
  }

  const handleReply = async (msgId, text) => {
    setSending(true)
    try {
      const { api } = await import('../../lib/api')
      await api.reply(msgId, text)
      onRefresh()
    } catch (error) {
      console.error('Failed to send reply:', error)
    } finally {
      setSending(false)
    }
  }

  const handleDismiss = async (msgId) => {
    try {
      const { api } = await import('../../lib/api')
      await api.dismiss(msgId)
      onRefresh()
    } catch (error) {
      console.error('Failed to dismiss:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Chat</h1>
          <p className="text-sm text-slate-400 mt-1">Collaborate with agents in real-time</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <Card>
            <div className="p-4 border-b border-slate-800">
              <Input
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                icon={SearchIcon}
              />
            </div>
            <div className="p-3 space-y-2 max-h-[calc(100vh-320px)] overflow-y-auto">
              {filteredChannels.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-slate-500">
                    {searchQuery ? 'No agents match your search' : 'No agents connected'}
                  </p>
                </div>
              ) : (
                filteredChannels.map((channel) => (
                  <AgentCard
                    key={channel.agent_id}
                    agent={{ ...channel, status: statuses[channel.agent_id] }}
                    isSelected={activeAgent === channel.agent_id}
                    pendingCount={getPendingCount(channel.agent_id)}
                    onClick={() => setActiveAgent(channel.agent_id)}
                  />
                ))
              )}
            </div>
          </Card>

          {activeAgent && (
            <Card>
              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-slate-300">Quick Stats</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Status</span>
                    <Badge variant={statuses[activeAgent] === 'running' ? 'success' : 'muted'}>
                      {statuses[activeAgent] || 'idle'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Messages</span>
                    <span className="text-slate-300">{channelMessages.length}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Pending</span>
                    <span className={getPendingCount(activeAgent) > 0 ? 'text-amber' : 'text-slate-300'}>
                      {getPendingCount(activeAgent)}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>

        <Card className="h-[calc(100vh-180px)]">
          {activeAgent ? (
            <MessageThread
              messages={channelMessages}
              activeAgent={activeAgent}
              onReply={handleReply}
              onDismiss={handleDismiss}
              replyText={replyText}
              setReplyText={setReplyText}
              sending={sending}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mb-4">
                <ChatIcon className="w-8 h-8 text-slate-600" />
              </div>
              <h3 className="text-lg font-medium text-slate-400">Select an Agent</h3>
              <p className="text-sm text-slate-500 mt-2 max-w-sm">
                Choose an agent from the left panel to view messages and collaborate.
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function SearchIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

function ChatIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}
