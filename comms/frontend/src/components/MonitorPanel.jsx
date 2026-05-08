import { useMemo } from 'react'
import { BriefcaseIcon, RocketIcon, WifiIcon, BookOpenIcon, ChartIcon } from './icons'
import { formatTime } from '../utils/formatTime'

export function MonitorPanel({ buildState, statuses, channels, events }) {
  const stats = useMemo(() => {
    const agentCount = channels?.length || 0
    const activeAgents = Object.entries(statuses).filter(([, s]) => s === 'running').length
    const blockedAgents = Object.entries(statuses).filter(([, s]) => s === 'blocked').length
    const idleAgents = agentCount - activeAgents - blockedAgents
    
    return { agentCount, activeAgents, blockedAgents, idleAgents }
  }, [channels, statuses])

  const recentEvents = useMemo(() => events?.slice(0, 10) || [], [events])

  return (
    <div className="flex-1 flex flex-col p-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="flex items-center gap-3 mb-6">
        <ChartIcon className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
        <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>System Monitor</h2>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard icon={BriefcaseIcon} label="Total Agents" value={stats.agentCount} />
        <StatCard icon={RocketIcon} label="Active" value={stats.activeAgents} />
        <StatCard icon={WifiIcon} label="Blocked" value={stats.blockedAgents} />
        <StatCard icon={BookOpenIcon} label="Idle" value={stats.idleAgents} />
      </div>

      {/* Build Status */}
      {buildState?.status && buildState.status !== 'idle' && (
        <BuildStatusCard buildState={buildState} />
      )}

      {/* Recent Events */}
      <RecentEvents events={recentEvents} />
    </div>
  )
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div 
      className="p-4 rounded-lg"
      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <Icon className="w-5 h-5 mb-2" style={{ color: 'var(--accent-primary)' }} />
      <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</div>
      <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</div>
    </div>
  )
}

function BuildStatusCard({ buildState }) {
  const statusColors = {
    running: 'var(--accent-primary)',
    done: 'var(--success)',
    error: 'var(--danger)',
    idle: 'var(--text-tertiary)',
  }

  return (
    <div 
      className="p-4 rounded-lg mb-6"
      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Build Status</span>
        <span 
          className="px-2 py-1 rounded text-xs font-medium"
          style={{ 
            background: statusColors[buildState.status] || statusColors.idle,
            color: 'var(--bg-primary)'
          }}
        >
          {buildState.status}
        </span>
      </div>
      {buildState.message && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{buildState.message}</p>
      )}
      {buildState.currentPhase && (
        <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
          Phase: {buildState.currentPhase}
          {buildState.currentIteration && ` | Iteration: ${buildState.currentIteration}`}
        </p>
      )}
    </div>
  )
}

function RecentEvents({ events }) {
  return (
    <div 
      className="flex-1 rounded-lg overflow-hidden"
      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-tertiary)' }}>
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Recent Events</span>
      </div>
      <div className="p-2 overflow-y-auto max-h-64">
        {events.length > 0 ? (
          events.map((event, idx) => (
            <EventRow key={idx} event={event} />
          ))
        ) : (
          <div className="px-3 py-4 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
            No recent events
          </div>
        )}
      </div>
    </div>
  )
}

function EventRow({ event }) {
  return (
    <div 
      className="px-3 py-2 rounded text-sm mb-1"
      style={{ background: 'var(--bg-primary)' }}
    >
      <span style={{ color: 'var(--text-tertiary)' }}>{formatTime(event.time)}</span>
      <span className="mx-2" style={{ color: 'var(--text-secondary)' }}>|</span>
      <span style={{ color: 'var(--text-secondary)' }}>{event.text}</span>
    </div>
  )
}
