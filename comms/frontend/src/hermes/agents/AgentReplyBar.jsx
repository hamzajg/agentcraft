import React, { useState, useRef, useEffect } from 'react'
import { Button } from '../ui'

export function AgentReplyBar({ onSend, hasPending, agentId, sending }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [text])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!text.trim() || sending) return
    onSend(text.trim())
    setText('')
  }

  return (
    <form onSubmit={handleSubmit} className="p-3 border-t border-slate-900 bg-[#0c1220] flex flex-col gap-2">
      <div className="relative flex items-end gap-2 p-2 bg-slate-950 border border-slate-800 rounded-lg focus-within:border-amber-500/40 transition-colors">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={hasPending ? `Reply to @${agentId}...` : 'Agent is idle...'}
          disabled={sending}
          rows={1}
          className="flex-1 max-h-[120px] bg-transparent border-none outline-none resize-none text-xs text-slate-100 placeholder-slate-600 font-sans py-1 px-1.5 focus:ring-0"
        />
        
        <Button
          type="submit"
          variant="gold"
          size="sm"
          disabled={sending || !text.trim()}
          className="h-7 w-7 !p-0 rounded flex items-center justify-center flex-shrink-0"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </Button>
      </div>

      <div className="flex justify-between items-center text-[10px] text-slate-500 px-1 font-mono">
        <span>Enter to send · Shift+Enter for line</span>
        {hasPending && (
          <span className="text-amber-400 font-bold animate-pulse">Waiting for your reply</span>
        )}
      </div>
    </form>
  )
}
