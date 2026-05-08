import { useState, useMemo } from 'react'
import { WifiIcon } from './icons'
import { formatTime } from '../utils/formatTime'
import { getEventTypeInfo } from '../utils/eventTypes'

const FILTERS = ['all', 'agent', 'build']

export function EventsBusPanel({ events, busMessages }) {
  const [filter, setFilter] = useState('all')

  const filteredEvents = useMemo(() => {
    return events?.filter(e => {
      if (filter === 'all') return true
      if (filter === 'agent') return e.type?.startsWith('agent_')
      if (filter === 'build') return ['build_started', 'build_done', 'phase_started', 'phase_done'].includes(e.type)
      return true
    }) || []
  }, [events, filter])

  return (
    <div className="flex-1 flex flex-col p-6" style={{ background: 'var(--bg-primary)' }}>
      <Header filter={filter} onFilterChange={setFilter} eventCount={filteredEvents.length} />
      <EventStream events={filteredEvents} />
    </div>
  )
}

function Header({ filter, onFilterChange, eventCount }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <WifiIcon className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
        <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Events Bus</h2>
      </div>
      <div className="flex items-center gap-2">
        {FILTERS.map(f => (
          <FilterButton
            key={f}
            filter={f}
            isActive={filter === f}
            onClick={() => onFilterChange(f)}
          />
        ))}
        <span className="text-xs ml-2" style={{ color: 'var(--text-tertiary)' }}>
          {eventCount} events
        </span>
      </div>
    </div>
  )
}

function FilterButton({ filter, isActive, onClick }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded text-sm font-medium capitalize"
      style={{
        background: isActive ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
        color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
        border: '1px solid var(--border-subtle)'
      }}
    >
      {filter}
    </button>
  )
}

function EventStream({ events }) {
  return (
    <div 
      className="flex-1 rounded-lg overflow-hidden"
      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <div 
        className="px-4 py-3 border-b"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-tertiary)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Event Stream</span>
      </div>
      <div className="p-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        {events && events.length > 0 ? (
          events.slice().reverse().map((event, idx) => (
            <EventItem key={idx} event={event} />
          ))
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  )
}

function EventItem({ event }) {
  const typeInfo = getEventTypeInfo(event.type)
  
  return (
    <div 
      className="px-3 py-2 rounded text-sm mb-1 flex items-start gap-3"
      style={{ background: 'var(--bg-primary)' }}
    >
      <TypeBadge typeInfo={typeInfo} />
      <div className="flex-1 min-w-0">
        <p style={{ color: 'var(--text-secondary)' }} className="truncate">{event.text}</p>
        {event.agent_id && (
          <AgentLabel agentId={event.agent_id} />
        )}
      </div>
      <TimeStamp time={event.time} />
    </div>
  )
}

function TypeBadge({ typeInfo }) {
  return (
    <span 
      className="px-1.5 py-0.5 rounded text-xs font-medium flex-shrink-0"
      style={{ 
        background: typeInfo.color + '20', 
        color: typeInfo.color 
      }}
    >
      {typeInfo.label}
    </span>
  )
}

function AgentLabel({ agentId }) {
  return (
    <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
      Agent: {agentId}
    </p>
  )
}

function TimeStamp({ time }) {
  return (
    <span className="text-xs flex-shrink-0" style={{ color: 'var(--text-tertiary)' }}>
      {formatTime(time)}
    </span>
  )
}

function EmptyState() {
  return (
    <div className="px-3 py-8 text-center" style={{ color: 'var(--text-tertiary)' }}>
      <WifiIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
      <p>No events to display</p>
    </div>
  )
}
