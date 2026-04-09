import { Card, CardBody, CardHeader, Badge, Button } from './ui'

export function TaskList({ tasks = [], onTaskClick }) {
  const groupedTasks = {
    pending: tasks.filter(t => t.status === 'pending'),
    running: tasks.filter(t => t.status === 'running'),
    completed: tasks.filter(t => t.status === 'completed'),
    blocked: tasks.filter(t => t.status === 'blocked'),
  }

  return (
    <div className="space-y-6">
      <TaskGroup 
        title="Running" 
        tasks={groupedTasks.running} 
        variant="success" 
        onTaskClick={onTaskClick}
      />
      <TaskGroup 
        title="Pending" 
        tasks={groupedTasks.pending} 
        variant="warning" 
        onTaskClick={onTaskClick}
      />
      <TaskGroup 
        title="Blocked" 
        tasks={groupedTasks.blocked} 
        variant="danger" 
        onTaskClick={onTaskClick}
      />
      <TaskGroup 
        title="Completed" 
        tasks={groupedTasks.completed} 
        variant="muted" 
        onTaskClick={onTaskClick}
      />
    </div>
  )
}

function TaskGroup({ title, tasks, variant, onTaskClick }) {
  if (tasks.length === 0) return null

  const variantStyles = {
    success: 'border-teal/30 bg-teal/5',
    warning: 'border-amber/30 bg-amber/5',
    danger: 'border-danger/30 bg-danger/5',
    muted: 'border-slate-800 bg-slate-900/50',
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-medium text-slate-300">{title}</h3>
        <span className="text-xs text-slate-500">({tasks.length})</span>
      </div>
      <div className="space-y-2">
        {tasks.map((task) => (
          <Card 
            key={task.id} 
            hover 
            className={`border ${variantStyles[variant]}`}
            onClick={() => onTaskClick?.(task)}
          >
            <CardBody className="p-3">
              <div className="flex items-center gap-3">
                <TaskStatusIcon status={task.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">
                    {task.title || task.description || task.task_id}
                  </p>
                  {task.agent_id && (
                    <p className="text-xs text-slate-500 mt-0.5">
                      Assigned to: <span className="font-mono text-slate-400">{task.agent_id}</span>
                    </p>
                  )}
                </div>
                {task.priority && (
                  <Badge variant={task.priority === 'high' ? 'danger' : 'default'}>
                    {task.priority}
                  </Badge>
                )}
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  )
}

function TaskStatusIcon({ status }) {
  const configs = {
    running: { icon: '◐', color: 'text-teal' },
    pending: { icon: '○', color: 'text-amber' },
    completed: { icon: '●', color: 'text-teal' },
    blocked: { icon: '✕', color: 'text-danger' },
  }
  
  const config = configs[status] || configs.pending

  return (
    <span className={`text-sm ${config.color} ${status === 'running' ? 'animate-pulse' : ''}`}>
      {config.icon}
    </span>
  )
}
