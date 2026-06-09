import React from 'react'
import { Avatar, Badge } from '../ui'

const ROLE_DESCRIPTIONS = {
  spec: 'Spec & requirements writer',
  architect: 'Systems & files architect',
  planner: 'Task planner & executor',
  backend_dev: 'Writes backend code',
  test_dev: 'Writes automated unit tests',
  config_agent: 'Manages dependencies & configs',
  docs_agent: 'Writes technical documents',
  reviewer: 'Reviews pull requests & specs',
  integration_test: 'Performs end-to-end testing',
  cicd: 'Configures build pipelines',
  hermes: 'Divine central coordinator',
}

export function AgentCard({ channel, status = 'idle', onClick }) {
  const { agent_id } = channel
  const desc = ROLE_DESCRIPTIONS[agent_id] || 'Specialist agent'

  // Standardize status text
  const isBlocked = status === 'blocked' || status === 'pending'
  const isRunning = status === 'active' || status === 'running'

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl border transition-all duration-200 flex items-start gap-4 hover:-translate-y-[1px]
        ${isBlocked 
          ? 'bg-amber-500/5 border-amber-500/30 hover:border-amber-500/50 shadow shadow-amber-500/5' 
          : isRunning
            ? 'bg-cyan-500/5 border-cyan-500/20 hover:border-cyan-500/40'
            : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700/80'}
      `}
    >
      {/* Status Ring Avatar */}
      <div className="relative">
        <Avatar name={agent_id} size="md" status={status} />
        {isBlocked && (
          <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-amber-500 border border-slate-950"></span>
          </span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="font-bold text-sm text-slate-100 capitalize font-mono">
            @{agent_id}
          </span>
          
          <div className="flex items-center gap-1.5">
            {isBlocked && (
              <Badge variant="gold">
                REPLY NEEDED
              </Badge>
            )}
            {isRunning && (
              <Badge variant="cyan" dot={true}>
                RUNNING
              </Badge>
            )}
          </div>
        </div>

        <p className="text-slate-400 text-xs truncate leading-normal">
          {desc}
        </p>
      </div>
    </button>
  )
}
