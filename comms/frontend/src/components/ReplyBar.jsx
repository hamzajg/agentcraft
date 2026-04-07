import { useState, useRef, useEffect } from 'react'

const AGENTS = ['spec', 'architect', 'planner', 'backend_dev', 'test_dev', 'config_agent', 'docs_agent', 'reviewer', 'integration_test', 'cicd']

export function ReplyBar({ pendingMsgId, agentLabel, onSend, disabled, channels = [] }) {
  const [text, setText] = useState('')
  const [mentions, setMentions] = useState([])
  const ref = useRef(null)

  // Auto-focus when a pending message arrives
  useEffect(() => {
    if (pendingMsgId) ref.current?.focus()
  }, [pendingMsgId])

  // Detect @mentions in text
  useEffect(() => {
    const matches = text.match(/@(\w+)/g) || []
    const agentIds = matches.map(m => m.slice(1)).filter(id => AGENTS.includes(id))
    setMentions(agentIds)
  }, [text])

  const send = () => {
    const t = text.trim()
    if (!t || !pendingMsgId) return
    onSend(t)
    setText('')
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const canSend = !!pendingMsgId && !!text.trim() && !disabled

  return (
    <div className="border-t border-border bg-panel px-4 py-3 space-y-2">
      {/* Mention hints */}
      {mentions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {mentions.map((agentId, i) => (
            <div key={i} className="text-xs bg-accent/20 border border-accent/50 rounded px-2 py-1 text-accent font-mono">
              @{agentId}
            </div>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex gap-3 items-end">
      <div className="flex-1 relative">
        <textarea
          ref={ref}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={onKey}
          placeholder={pendingMsgId
              ? `Reply (mention agents with @agent)…`
            : 'No pending questions'}
          disabled={!pendingMsgId || disabled}
          rows={1}
          className="
            w-full bg-surface border border-border rounded-lg
            px-4 py-2.5 text-sm text-gray-200 resize-none
            placeholder:text-muted
            focus:outline-none focus:border-accent/60
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors leading-relaxed
            min-h-[44px] max-h-40
          "
          style={{ fieldSizing: 'content' }}
        />
        <p className="absolute right-3 bottom-2 text-[10px] text-muted select-none">
          {pendingMsgId ? '↵ send' : ''}
        </p>
      </div>
      <button
        onClick={send}
        disabled={!canSend}
        className="
          h-[44px] px-5 rounded-lg text-sm font-medium
          bg-accent hover:bg-accent/90 text-white
          disabled:opacity-30 disabled:cursor-not-allowed
          transition-all active:scale-95
        "
      >
        Send
      </button>
    </div>
    </div>
  )
}
