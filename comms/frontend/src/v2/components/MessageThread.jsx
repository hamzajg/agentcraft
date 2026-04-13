import { useState, useEffect, useRef, useCallback, useMemo, useLayoutEffect } from 'react'
import { api } from '../../lib/api'
import { Card, CardBody, CardHeader, Badge, Button } from './ui'
import { Avatar } from './ui/Avatar'

/* ─── Fluent UI Message Thread ───
   - Fluent 2 message bubbles with clear visual hierarchy
   - Reactive hover/active states
   - Smooth infinite scroll
   - Pending/resolved message states
*/

export function MessageThread({ messages: propMessages, activeAgent, onReply, onDismiss, replyText, setReplyText, sending }) {
  const [olderMessages, setOlderMessages] = useState([])
  const [recentMessages, setRecentMessages] = useState([])
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [oldestCursor, setOldestCursor] = useState(null)
  const [userScrolledUp, setUserScrolledUp] = useState(false)
  const containerRef = useRef(null)
  const bottomRef = useRef(null)
  const sentinelRef = useRef(null)

  const visibleMessages = useMemo(() => {
    const seen = new Set()
    const items = []
    ;[...olderMessages, ...recentMessages, ...propMessages].forEach(m => {
      if (!seen.has(m.id)) {
        seen.add(m.id)
        items.push(m)
      }
    })
    return items.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  }, [olderMessages, recentMessages, propMessages])

  const pendingMessage = visibleMessages.find(m => m.status === 'pending')

  const loadRecent = async () => {
    if (!activeAgent) return
    try {
      const data = await api.older(activeAgent, null, 50)
      const msgs = data.reverse()
      setRecentMessages(msgs)
      if (msgs.length > 0) {
        const oldest = msgs.reduce((min, m) => new Date(m.created_at) < new Date(min.created_at) ? m : min)
        setOldestCursor(oldest.created_at)
        setHasMore(data.length === 50)
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
      if (older.length === 0) { setHasMore(false); return }
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

  useEffect(() => { loadRecent() }, [activeAgent])

  const handleScroll = useCallback(e => {
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

  useLayoutEffect(() => {
    if (!userScrolledUp && bottomRef.current && containerRef.current) {
      requestAnimationFrame(() => bottomRef.current.scrollIntoView({ behavior: 'smooth' }))
    }
  }, [visibleMessages.length, userScrolledUp])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!pendingMessage || !replyText.trim()) return
    await onReply(pendingMessage.id, replyText)
    setReplyText('')
  }

  return (
    <div className="flex flex-col h-full bg-fluent-surface">
      {/* Header */}
      <CardHeader className="flex-shrink-0 border-b border-fluent-borderSubtle">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar name={activeAgent} size="md" />
            <div>
              <h2 className="font-semibold text-fluent-text">{activeAgent || 'Select Agent'}</h2>
              <p className="text-xs text-fluent-textTert">
                {propMessages.length} message{propMessages.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          {pendingMessage && (
            <Badge variant="warning" dot>Needs response</Badge>
          )}
        </div>
      </CardHeader>

      {/* Messages */}
      <CardBody
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-3 p-4 bg-fluent-bg">
        {loadingOlder && (
          <div className="flex items-center justify-center py-3">
            <div className="w-4 h-4 border-2 border-fluent-accent border-t-transparent rounded-full animate-spin" />
            <span className="ml-2 text-xs text-fluent-textTert">Loading older…</span>
          </div>
        )}
        {hasMore && userScrolledUp && <div ref={sentinelRef} className="h-1" />}

        {visibleMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="w-16 h-16 rounded-fluent-xl bg-fluent-card flex items-center justify-center mb-4">
              <MessageIcon className="w-8 h-8 text-fluent-textTert" />
            </div>
            <h3 className="text-base font-medium text-fluent-textSec">No messages yet</h3>
            <p className="text-sm text-fluent-textTert mt-1.5 max-w-xs">
              Await a clarification request from {activeAgent || 'the agent'} to start collaborating.
            </p>
          </div>
        ) : (
          visibleMessages.map((msg) => (
            <FluentMessageBubble key={msg.id} msg={msg} onDismiss={onDismiss} />
          ))
        )}
        <div ref={bottomRef} />
      </CardBody>

      {/* Reply bar */}
      <div className="flex-shrink-0 border-t border-fluent-borderSubtle p-3 bg-fluent-surfaceAlt">
        <form onSubmit={handleSubmit} className="space-y-2.5">
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder={pendingMessage
              ? 'Compose your response…'
              : 'No pending requests. Await the next clarification.'
            }
            disabled={!pendingMessage || sending}
            rows={3}
            className="w-full bg-fluent-surface border border-fluent-border rounded-fluent-lg px-4 py-2.5
                       text-sm text-fluent-text placeholder:text-fluent-textTert
                       focus:outline-none focus:border-fluent-accentBorder focus:ring-1 focus:ring-fluent-accent/20
                       resize-none disabled:opacity-40 transition-all duration-150 font-sans"
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-fluent-textTert">
              {pendingMessage ? `Replying to ${activeAgent}` : 'Idle'}
            </p>
            <Button
              type="submit"
              disabled={!pendingMessage || sending || !replyText.trim()}
              size="sm"
              className="flex items-center gap-1.5"
            >
              {sending ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/60 border-t-transparent rounded-full animate-spin" />
                  Sending…
                </>
              ) : (
                <>
                  <SendIcon />
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

/* ═══════════════════════════════════════════
   Fluent Message Bubble
   ═══════════════════════════════════════════ */

function FluentMessageBubble({ msg, onDismiss }) {
  const isPending = msg.status === 'pending'
  const timeAgo = formatTimeAgo(msg.created_at)

  return (
    <div
      className={`rounded-fluent-xl border p-4 transition-all duration-150 animate-slide-up
        ${isPending
          ? 'border-fluent-warningBorder bg-fluent-warningBg'
          : 'border-fluent-borderSubtle bg-fluent-surfaceAlt/70 hover:bg-fluent-surfaceAlt hover:shadow-fluent-card'
        }`}
    >
      {/* Meta row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Avatar name={msg.agent_id} size="sm" />
          <span className="text-xs font-medium text-fluent-textSec">{msg.agent_label || msg.agent_id}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-fluent-textTert">{timeAgo}</span>
          {isPending ? (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-fluent-warningBg border border-fluent-warningBorder text-fluent-warning text-[10px] font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-fluent-warning animate-pulse" />
              Pending
            </span>
          ) : msg.status === 'replied' ? (
            <span className="px-2 py-0.5 rounded-full bg-fluent-success/10 border border-fluent-success/20 text-fluent-success text-[10px] font-semibold">
              Resolved
            </span>
          ) : null}
        </div>
      </div>

      {/* Question */}
      {msg.question && (
        <p className="text-sm text-fluent-text leading-relaxed whitespace-pre-wrap mb-2">
          {msg.question}
        </p>
      )}

      {/* File attachment */}
      {msg.file && (
        <div className="flex items-center gap-2 text-xs bg-fluent-surface rounded-fluent-lg border border-fluent-borderSubtle px-3 py-2 w-fit">
          <FileIcon className="w-4 h-4 text-fluent-textTert" />
          <span className="font-mono text-fluent-textSec">{msg.file}</span>
        </div>
      )}

      {/* Suggestions */}
      {msg.suggestions?.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-2 mt-2 border-t border-fluent-borderSubtle">
          {msg.suggestions.map((s, i) => (
            <button
              key={i}
              className="text-xs px-3 py-1.5 rounded-fluent-lg border border-fluent-accentBorder text-fluent-accent
                         hover:bg-fluent-accentSubtle transition-all duration-150 active:scale-[0.97]"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Reply */}
      {msg.reply && (
        <div className="mt-3 pt-3 border-t border-fluent-borderSubtle">
          <p className="text-xs text-fluent-success mb-1.5 font-medium">Your response:</p>
          <p className="text-sm text-fluent-text leading-relaxed whitespace-pre-wrap">{msg.reply}</p>
        </div>
      )}

      {/* Dismiss */}
      {!isPending && onDismiss && (
        <button
          onClick={() => onDismiss(msg.id)}
          className="mt-3 text-xs text-fluent-textTert hover:text-fluent-textSec transition-colors"
        >
          Dismiss
        </button>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════
   Helpers & Icons
   ═══════════════════════════════════════════ */

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
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
