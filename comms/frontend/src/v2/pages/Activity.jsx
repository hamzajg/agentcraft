import { Card, CardBody, Badge, Button, Input } from '../components/ui'
import { EventFeed } from '../components/EventFeed'
import { useState, useMemo } from 'react'

export function Activity({ events }) {
  const [filter, setFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredEvents = useMemo(() => {
    let result = events
    
    if (filter !== 'all') {
      result = result.filter(e => e.type === filter)
    }
    
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      result = result.filter(e => 
        (e.text || '').toLowerCase().includes(q) ||
        (e.content || '').toLowerCase().includes(q) ||
        (e.agent_id || '').toLowerCase().includes(q)
      )
    }
    
    return result
  }, [events, filter, searchQuery])

  const eventTypes = useMemo(() => {
    const types = {}
    events.forEach(e => {
      const type = e.type || 'unknown'
      types[type] = (types[type] || 0) + 1
    })
    return Object.entries(types).sort((a, b) => b[1] - a[1])
  }, [events])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Activity</h1>
          <p className="text-sm text-slate-400 mt-1">Real-time event stream from all agents</p>
        </div>
        <Button variant="secondary" size="sm">
          <RefreshIcon className="w-4 h-4" />
          Clear Events
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <div className="space-y-4">
          <Card>
            <div className="p-4 border-b border-slate-800">
              <Input
                placeholder="Search events..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                icon={SearchIcon}
              />
            </div>
            <div className="p-3">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">Filter by Type</p>
              <div className="space-y-1">
                <FilterButton 
                  label="All Events" 
                  count={events.length}
                  isActive={filter === 'all'}
                  onClick={() => setFilter('all')}
                />
                {eventTypes.map(([type, count]) => (
                  <FilterButton
                    key={type}
                    label={formatType(type)}
                    count={count}
                    isActive={filter === type}
                    onClick={() => setFilter(type)}
                  />
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <CardBody className="p-4">
              <h3 className="text-sm font-medium text-slate-300 mb-3">Event Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Total Events</span>
                  <span className="text-slate-300">{events.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Unique Types</span>
                  <span className="text-slate-300">{eventTypes.length}</span>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>

        <EventFeed events={filteredEvents} maxHeight="calc(100vh - 200px)" />
      </div>
    </div>
  )
}

function FilterButton({ label, count, isActive, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm
        transition-colors
        ${isActive 
          ? 'bg-accent/10 text-accent' 
          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
        }
      `}
    >
      <span>{label}</span>
      <span className={`text-xs ${isActive ? 'text-accent' : 'text-slate-500'}`}>{count}</span>
    </button>
  )
}

function formatType(type) {
  return type
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function SearchIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

function RefreshIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  )
}
