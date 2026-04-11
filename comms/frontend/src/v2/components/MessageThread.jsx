import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { api } from '../../lib/api'
import { Card, CardBody, CardHeader, Badge, Button } from './ui'
import { Avatar } from './ui/Avatar'

export function MessageThread({ messages: propMessages, activeAgent, onReply, onDismiss, replyText, setReplyText, sending }) {
  // Infinite scroll state
  const [olderMessages, setOlderMessages] = useState([])
  const [recentMessages, setRecentMessages] = useState([])
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [oldestCursor, setOldestCursor] = useState(null)
  const [userScrolledUp, setUserScrolledUp] = useState(false)
  const containerRef = useRef(null)
  const bottomRef = useRef(null)
  const sentinelRef = useRef(null)

  const allMessages = [...recentMessages, ...propMessages]
  const visibleMessages = useMemo(() => allMessages.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)), [allMessages])

  const pendingMessage = visibleMessages.find(m => m.status === 'pending')

  const loadRecent = async () => {
    if (!activeAgent) return
    try {
      const msgs = await api.messages(activeAgent)
      setRecentMessages(msgs)
      if (msgs.length > 0) {
        const oldest = msgs.reduce((min, m) => new Date(m.created_at) < new Date(min.created_at) ? m : min)
        setOldestCursor(oldest.created_at)
        setHasMore(true)
      }
    } catch (e) {
      console.error('load recent failed', e)
    }
  }

  const loadOlder = async () => {
    if (loadingOlder || !hasMore || !activeAgent) return
    setLoadingOlder(true)
    try {
      const older = await api.older(activeAgent, oldestCursor, 20)
      if (older.length === 0) {
        setHasMore(false)
        return
      }
      const reversed = older.reverse()
      setOlderMessages(prev => [...reversed, ...prev])
      const allOlder = [...older, ...olderMessages]
      const newOldest = allOlder.reduce((min, m) => new Date(m.created_at) < new Date(min.created_at) ? m : min)
      setOldestCursor(newOldest.created_at)
      setHasMore(older.length === 20)
    } catch (e) {
      console.error('load older failed', e)
    } finally {
      setLoadingOlder(false)
    }
  }

  useEffect(() => {
    loadRecent()
  }, [activeAgent])

  const handleScroll = useCallback((e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    setUserScrolledUp(distanceFromBottom > 200)
  }, [])

  useEffect(() => {
    if (!sentinelRef.current || !hasMore || loadingOlder) return
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && userScrolledUp && loadOlder(),
      { root: containerRef.current, rootMargin: '200px 0px 0px 0px' }
    )
    observer.observe(sentinelRef.current)
    return () => observer.disconnect()
  }, [loadOlder, hasMore, loadingOlder, userScrolledUp])

  useEffect(() => {
    if (!userScrolledUp) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [visibleMessages.length, userScrolledUp])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!pendingMessage || !replyText.trim()) return
    await onReply(pendingMessage.id, replyText)
    setReplyText('')
  }

  return (
    <div className="flex flex-col h-full">
      <CardHeader className="flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar name={activeAgent} size="md" />
            <div>
              <h2 className="font-semibold text-slate-100">{activeAgent || 'Select Agent'}</h2>
              <p className="text-xs text-slate-500">
                {messages.length} message{messages.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          {pendingMessage && (
            <Badge variant="warning" dot>Needs response</Badge>
          )}
        </div>
      </CardHeader>

      <CardBody 
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-4 p-5">
        {loadingOlder && (
          <div className="flex items-center justify-center py-4">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="ml-2 text-sm text-slate-500">Loading older...</span>
          </div>
        )}
        {hasMore && userScrolledUp && <div ref={sentinelRef} className="h-1" />}
        {visibleMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mb-4">
              <MessageIcon className="w-8 h-8 text-slate-600" />
            </div>
            <h3 className="text-lg font-medium text-slate-400">No messages yet</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-xs">
              Await a clarification request from {activeAgent || 'the agent'} to start collaborating.
            </p>
          </div>
        ) : (
          visibleMessages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} onDismiss={onDismiss} />
          ))
        )}
        <div ref={bottomRef} />
      </CardBody>

      <div className="flex-shrink-0 border-t border-slate-800 p-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder={pendingMessage 
              ? 'Compose your response...' 
              : 'No pending requests. Await the next clarification.'
            }
            disabled={!pendingMessage || sending}
            rows={3}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 resize-none disabled:opacity-40"
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              {pendingMessage ? `Replying to ${activeAgent}` : 'Idle'}
            </p>
            <Button
              type="submit"
              disabled={!pendingMessage || sending || !replyText.trim()}
              size="sm"
            >
              {sending ? (
                <>
                  <Spinner className="w-4 h-4" />
                  Sending...
                </>
              ) : (
                <>
                  <SendIcon className="w-4 h-4" />
                  Send Reply
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function MessageBubble({ msg, onDismiss }) {
  const isPending = msg.status === 'pending'
  const timeAgo = formatTimeAgo(msg.created_at)

  return (
    <div className={`
      rounded-xl border p-4
      ${isPending ? 'border-amber/30 bg-amber/5' : 'border-slate-800 bg-slate-900/50'}
      animate-fade-in
    `}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Avatar name={msg.agent_id} size="sm" />
          <span className="text-xs font-medium text-slate-400">{msg.agent_label || msg.agent_id}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">{timeAgo}</span>
          {isPending ? (
            <Badge variant="warning">Pending</Badge>
          ) : msg.status === 'replied' ? (
            <Badge variant="success">Resolved</Badge>
          ) : null}
        </div>
      </div>

      <div className="space-y-3">
        {msg.question && (
          <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
            {msg.question}
          </p>
        )}
        
        {msg.file && (
          <div className="flex items-center gap-2 text-xs bg-slate-800/50 rounded-lg px-3 py-2 w-fit">
            <FileIcon className="w-4 h-4 text-slate-500" />
            <span className="font-mono text-slate-400">{msg.file}</span>
          </div>
        )}

        {msg.suggestions?.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {msg.suggestions.map((s, i) => (
              <button
                key={i}
                className="text-xs px-3 py-1 rounded-full border border-accent/30 text-accent hover:bg-accent/10 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {msg.reply && (
          <div className="mt-3 pt-3 border-t border-slate-800">
            <p className="text-xs text-teal mb-1 font-medium">Your response:</p>
            <p className="text-sm text-slate-300">{msg.reply}</p>
          </div>
        )}
      </div>

      {!isPending && onDismiss && (
        <button
          onClick={() => onDismiss(msg.id)}
          className="mt-3 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          Dismiss
        </button>
      )}
    </div>
  )
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return 'Unknown'
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return new Date(timestamp).toLocaleDateString()
}

function MessageIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function SendIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function FileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function Spinner({ className }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}
