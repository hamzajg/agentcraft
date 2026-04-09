import { useState, useMemo } from 'react'
import { Card, CardBody, Badge, Button, Input, Avatar, StatusBadge } from '../components/ui'

const AGENT_ROLES = {
  spec: { role: 'Spec Agent', description: 'Gathers and refines project specifications' },
  architect: { role: 'Architect', description: 'Designs system architecture and technical decisions' },
  supervisor: { role: 'Supervisor', description: 'Oversees overall project execution and coordination' },
  planner: { role: 'Planner', description: 'Creates execution plans and task breakdowns' },
  backend_dev: { role: 'Backend Developer', description: 'Implements server-side logic and APIs' },
  test_dev: { role: 'Test Engineer', description: 'Creates and maintains test suites' },
  config_agent: { role: 'Config Agent', description: 'Manages configuration and environment settings' },
  docs_agent: { role: 'Documentation Agent', description: 'Generates and maintains documentation' },
  integration_test: { role: 'Integration Test Agent', description: 'Runs integration and end-to-end tests' },
  reviewer: { role: 'Reviewer', description: 'Reviews code and provides feedback' },
  cicd: { role: 'CI/CD Agent', description: 'Manages continuous integration and deployment' },
}

export function Agents({ channels, statuses }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const allAgents = useMemo(() => {
    const agents = new Map()
    
    channels.forEach(ch => {
      agents.set(ch.agent_id, {
        agent_id: ch.agent_id,
        agent_label: ch.agent_label || AGENT_ROLES[ch.agent_id]?.role || ch.agent_id,
        description: ch.description || AGENT_ROLES[ch.agent_id]?.description || '',
        status: statuses[ch.agent_id] || 'idle',
        last_active: ch.last_active,
        unread: ch.unread || 0,
      })
    })
    
    Object.entries(AGENT_ROLES).forEach(([id, info]) => {
      if (!agents.has(id)) {
        agents.set(id, {
          agent_id: id,
          agent_label: info.role,
          description: info.description,
          status: statuses[id] || 'idle',
          last_active: null,
          unread: 0,
        })
      }
    })
    
    return Array.from(agents.values())
  }, [channels, statuses])

  const filteredAgents = useMemo(() => {
    let result = allAgents
    
    if (statusFilter !== 'all') {
      result = result.filter(a => a.status === statusFilter)
    }
    
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      result = result.filter(a => 
        a.agent_id.toLowerCase().includes(q) ||
        a.agent_label.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q)
      )
    }
    
    return result
  }, [allAgents, statusFilter, searchQuery])

  const runningCount = allAgents.filter(a => a.status === 'running').length
  const idleCount = allAgents.filter(a => a.status === 'idle').length
  const blockedCount = allAgents.filter(a => a.status === 'blocked').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Agents</h1>
          <p className="text-sm text-slate-400 mt-1">Manage and monitor your agent workforce</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <StatCard title="Total Agents" value={allAgents.length} />
        <StatCard title="Running" value={runningCount} variant="success" />
        <StatCard title="Idle" value={idleCount} variant="muted" />
        <StatCard title="Blocked" value={blockedCount} variant={blockedCount > 0 ? 'danger' : 'muted'} />
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search agents by name, role, or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            icon={SearchIcon}
          />
        </div>
        <div className="flex gap-2">
          {['all', 'running', 'idle', 'blocked'].map(status => (
            <Button
              key={status}
              variant={statusFilter === status ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setStatusFilter(status)}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredAgents.map((agent) => (
          <Card key={agent.agent_id} hover>
            <CardBody className="p-5">
              <div className="flex items-start gap-4">
                <Avatar name={agent.agent_id} size="lg" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-slate-100 truncate">
                      {agent.agent_label}
                    </h3>
                    <StatusBadge status={agent.status} />
                  </div>
                  <p className="text-xs text-slate-500 font-mono mb-2">{agent.agent_id}</p>
                  <p className="text-sm text-slate-400 line-clamp-2">
                    {agent.description}
                  </p>
                </div>
              </div>
              {agent.last_active && (
                <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
                  <span>Last active</span>
                  <span>{formatTimeAgo(agent.last_active)}</span>
                </div>
              )}
            </CardBody>
          </Card>
        ))}
      </div>

      {filteredAgents.length === 0 && (
        <Card>
          <CardBody className="py-12 text-center">
            <div className="w-12 h-12 rounded-xl bg-slate-800 mx-auto mb-4 flex items-center justify-center">
              <SearchIcon className="w-6 h-6 text-slate-600" />
            </div>
            <h3 className="text-lg font-medium text-slate-400">No agents found</h3>
            <p className="text-sm text-slate-500 mt-1">
              Try adjusting your search or filter criteria
            </p>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

function StatCard({ title, value, variant = 'default' }) {
  const variants = {
    default: 'border-slate-800',
    success: 'border-teal/30 bg-teal/5',
    muted: 'border-slate-800 bg-slate-900/50',
    danger: 'border-danger/30 bg-danger/5',
  }

  return (
    <Card className={variants[variant]}>
      <CardBody className="p-4">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
        <p className="text-2xl font-bold text-slate-100 mt-1">{value}</p>
      </CardBody>
    </Card>
  )
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return 'Never'
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function SearchIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}
