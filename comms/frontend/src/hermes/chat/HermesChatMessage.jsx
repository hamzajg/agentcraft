import React from 'react'
import { Avatar } from '../ui'

export function HermesChatMessage({ message }) {
  const { question, reply, created_at, agent_id } = message
  const timestamp = created_at ? new Date(created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''

  return (
    <div className="flex flex-col gap-4 py-2 animate-[message-fly_0.25s_ease-out]">
      {/* 1. Human Question (aligned right) */}
      {question && (
        <div className="flex justify-end items-start gap-3 max-w-[85%] ml-auto">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-slate-500 font-mono mb-1">Human</span>
            <div className="px-4 py-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-slate-100 text-sm whitespace-pre-wrap leading-relaxed shadow-sm shadow-amber-500/5">
              {question}
            </div>
            {timestamp && <span className="text-[9px] text-slate-600 font-mono mt-1">{timestamp}</span>}
          </div>
          <Avatar name="Human" size="sm" />
        </div>
      )}

      {/* 2. Hermes Response (aligned left) */}
      {reply && (
        <div className="flex justify-start items-start gap-3 max-w-[85%]">
          <Avatar name="Hermes" size="sm" />
          <div className="flex flex-col items-start">
            <span className="text-[10px] text-amber-400 font-semibold font-serif tracking-wider mb-1" style={{ fontFamily: 'var(--font-hermes)' }}>
              Hermes
            </span>
            <div className="px-4 py-2.5 rounded-2xl bg-slate-900 border border-slate-800 text-slate-100 text-sm whitespace-pre-wrap leading-relaxed shadow-md">
              {/* Parse routing mention format if present, e.g. [Hermes -> @agent_id] */}
              {reply.includes('[@') || reply.includes('→ @') ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs text-cyan-400 font-mono px-2 py-1 rounded bg-cyan-950/20 border border-cyan-800/20 w-fit">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    <span>Routing delegation</span>
                  </div>
                  <p>{reply}</p>
                </div>
              ) : (
                reply
              )}
            </div>
            {timestamp && <span className="text-[9px] text-slate-600 font-mono mt-1">{timestamp}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
