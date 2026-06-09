import React, { useState, useRef, useEffect } from 'react'
import { Button } from '../ui'

export function HermesChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    // Auto-resize the textarea height based on content
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
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
    if (!text.trim() || disabled) return
    onSend(text.trim())
    setText('')
  }

  return (
    <form onSubmit={handleSubmit} className="relative flex items-end gap-2 p-3 bg-slate-950 border border-slate-800/80 rounded-xl focus-within:border-amber-500/50 focus-within:shadow-lg focus-within:shadow-amber-500/5 transition-all duration-200">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Tell Hermes what to build..."
        disabled={disabled}
        rows={1}
        className="flex-1 max-h-[180px] bg-transparent border-none outline-none resize-none text-sm text-slate-100 placeholder-slate-500 font-sans py-1.5 px-2 focus:ring-0"
      />
      <Button
        type="submit"
        variant="primary"
        size="sm"
        disabled={disabled || !text.trim()}
        className="h-8 w-8 !p-0 rounded-lg flex items-center justify-center flex-shrink-0"
      >
        <svg className="w-4 h-4 transform rotate-90" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </Button>
    </form>
  )
}
