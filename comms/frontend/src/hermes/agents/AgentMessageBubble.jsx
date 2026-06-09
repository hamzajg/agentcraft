import React from 'react'
import { Avatar, Badge } from '../ui'

export function AgentMessageBubble({ msg, isPending, reply, suggestions = [], onSuggest }) {
  const { question, file, created_at, agent_id } = msg
  const timestamp = created_at ? new Date(created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''

  return (
    <div className="flex flex-col gap-4 py-1 animate-[message-fly_0.25s_ease-out]">
      {/* 1. Agent Question (left-aligned) */}
      {question && (
        <div className="flex justify-start items-start gap-2.5 max-w-[85%]">
          <Avatar name={agent_id} size="sm" />
          <div className="flex flex-col items-start">
            <div 
              className={`
                px-3 py-2 rounded-2xl bg-slate-900 border text-slate-100 text-xs leading-relaxed shadow-sm
                ${isPending && !reply 
                  ? 'border-amber-500/30 shadow-md shadow-amber-500/5 hermes-glow' 
                  : 'border-slate-800'}
              `}
            >
              {/* Optional File Attachment banner */}
              {file && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-950 border border-slate-800 text-[10px] text-cyan-400 font-mono mb-2">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="truncate" title={file}>{file.split('/').pop()}</span>
                </div>
              )}
              
              <p className="whitespace-pre-wrap">{question}</p>
            </div>
            
            {timestamp && <span className="text-[8px] text-slate-600 font-mono mt-1 ml-1">{timestamp}</span>}

            {/* Quick reply suggestions */}
            {isPending && !reply && suggestions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2 ml-1">
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => onSuggest(s)}
                    className="px-2 py-1 rounded-md border border-slate-800 hover:border-amber-500/30 bg-slate-950 hover:bg-[#0c1220] text-[10px] text-slate-400 hover:text-amber-400 font-medium transition-all duration-200"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. Human Reply (right-aligned) */}
      {reply && (
        <div className="flex justify-end items-start gap-2.5 max-w-[85%] ml-auto">
          <div className="flex flex-col items-end">
            <div className="px-3 py-2 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-slate-100 text-xs leading-relaxed shadow-sm">
              <p className="whitespace-pre-wrap">{reply}</p>
            </div>
            <span className="text-[8px] text-slate-600 font-mono mt-1 mr-1">User</span>
          </div>
          <Avatar name="Human" size="sm" />
        </div>
      )}
    </div>
  )
}
