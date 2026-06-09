import React, { useRef, useEffect } from 'react'
import { HermesChatMessage } from './HermesChatMessage'
import { HermesChatInput } from './HermesChatInput'
import { Spinner } from '../ui'
import hermesLogo from '../assets/hermes_logo.png'

const QUICK_STARTS = [
  'Create a new REST endpoint for user registration',
  'Write unit tests for the main database schema helper',
  'Build a glowing landing page hero section with pure CSS',
]

export function HermesChat({ messages = [], onSendMessage, sending }) {
  const bottomRef = useRef(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-full bg-[#07090f] relative">
      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 hermes-scrollbar">
        {messages.length === 0 ? (
          /* Empty/Welcome State */
          <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto py-12">
            <img 
              src={hermesLogo} 
              alt="Hermes Wing Logo" 
              className="w-16 h-16 object-contain rounded-xl border border-amber-500/20 shadow-xl shadow-amber-500/5 mb-6 animate-pulse" 
            />
            <h2 className="text-2xl font-bold font-serif text-white mb-2" style={{ fontFamily: 'var(--font-hermes)' }}>
              I am Hermes
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed mb-8">
              Describe your software engineering goal, and I will dispatch work, coordinate specialist agents, and monitor execution.
            </p>

            <div className="w-full flex flex-col gap-2.5">
              {QUICK_STARTS.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(q)}
                  className="w-full text-left p-3.5 rounded-lg border border-slate-800 hover:border-amber-500/30 bg-slate-900/40 hover:bg-[#0c1220] text-xs text-slate-300 hover:text-amber-400 font-medium transition-all duration-200"
                >
                  {q} &rarr;
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Render Chat History */
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg) => (
              <HermesChatMessage key={msg.id} message={msg} />
            ))}
            
            {sending && (
              <div className="flex items-center gap-2 text-xs text-slate-500 font-mono italic">
                <Spinner size="sm" />
                <span>Hermes is thinking...</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-slate-900 bg-[#07090f]">
        <div className="max-w-3xl mx-auto">
          <HermesChatInput onSend={onSendMessage} disabled={sending} />
        </div>
      </div>
    </div>
  )
}
