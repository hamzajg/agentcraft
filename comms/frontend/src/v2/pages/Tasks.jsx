import { useState } from 'react'
import { Card, CardBody, Badge, Button, Input } from '../components/ui'
import { TaskList } from '../components/TaskList'

export function Tasks({ tasks = [], events = [] }) {
  const [filter, setFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')

  const derivedTasks = events
    .filter(e => e.type?.includes('task') || e.type?.includes('phase') || e.type?.includes('iter'))
    .map((e, idx) => ({
      id: e.id || `task-${idx}`,
      title: e.text || e.content || e.message || formatEventType(e.type),
      description: e.description || '',
      status: getStatusFromEvent(e.type),
      agent_id: e.agent_id,
      priority: e.priority || 'normal',
    }))

  const allTasks = [...tasks, ...derivedTasks]

  const filteredTasks = allTasks.filter(task => {
    if (filter !== 'all' && task.status !== filter) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      return (
        (task.title || '').toLowerCase().includes(q) ||
        (task.description || '').toLowerCase().includes(q) ||
        (task.agent_id || '').toLowerCase().includes(q)
      )
    }
    return true
  })

  const taskStats = {
    total: allTasks.length,
    running: allTasks.filter(t => t.status === 'running').length,
    pending: allTasks.filter(t => t.status === 'pending').length,
    completed: allTasks.filter(t => t.status === 'completed').length,
    blocked: allTasks.filter(t => t.status === 'blocked').length,
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Tasks</h1>
          <p className="text-sm text-slate-400 mt-1">Track and manage agent tasks</p>
        </div>
        <Button variant="secondary" size="sm">
          <PlusIcon className="w-4 h-4" />
          New Task
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-5">
        <StatCard title="Total" value={taskStats.total} />
        <StatCard title="Running" value={taskStats.running} variant="success" />
        <StatCard title="Pending" value={taskStats.pending} variant="warning" />
        <StatCard title="Completed" value={taskStats.completed} variant="muted" />
        <StatCard title="Blocked" value={taskStats.blocked} variant={taskStats.blocked > 0 ? 'danger' : 'muted'} />
      </div>

      <Card>
        <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Input
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              icon={SearchIcon}
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {['all', 'running', 'pending', 'completed', 'blocked'].map(status => (
              <Button
                key={status}
                variant={filter === status ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setFilter(status)}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </Button>
            ))}
          </div>
        </div>
        <CardBody className="p-5">
          {filteredTasks.length > 0 ? (
            <TaskList tasks={filteredTasks} />
          ) : (
            <div className="text-center py-12">
              <div className="w-12 h-12 rounded-xl bg-slate-800 mx-auto mb-4 flex items-center justify-center">
                <TaskIcon className="w-6 h-6 text-slate-600" />
              </div>
              <h3 className="text-lg font-medium text-slate-400">No tasks found</h3>
              <p className="text-sm text-slate-500 mt-1">
                Tasks will appear here as agents work on them
              </p>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function StatCard({ title, value, variant = 'default' }) {
  const variants = {
    default: 'border-slate-800',
    success: 'border-teal/30 bg-teal/5',
    warning: 'border-amber/30 bg-amber/5',
    muted: 'border-slate-800 bg-slate-900/50',
    danger: 'border-danger/30 bg-danger/5',
  }

  return (
    <div className={`rounded-xl border p-4 ${variants[variant]}`}>
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
      <p className="text-2xl font-bold text-slate-100 mt-1">{value}</p>
    </div>
  )
}

function getStatusFromEvent(type) {
  if (type?.includes('started') || type?.includes('running')) return 'running'
  if (type?.includes('done') || type?.includes('completed')) return 'completed'
  if (type?.includes('blocked')) return 'blocked'
  return 'pending'
}

function formatEventType(type) {
  if (!type) return 'Unknown task'
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

function PlusIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function TaskIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  )
}
