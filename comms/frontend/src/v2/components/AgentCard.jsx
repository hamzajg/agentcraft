import { Card, CardBody, Avatar, StatusBadge, Badge } from './ui'

export function AgentCard({ agent, isSelected, onClick, pendingCount = 0 }) {
  return (
    <Card
      hover
      className={`
        cursor-pointer transition-all duration-150
        ${isSelected ? 'border-accent/50 bg-accent/5' : ''}
      `}
      onClick={onClick}
    >
      <CardBody className="p-4">
        <div className="flex items-start gap-4">
          <Avatar name={agent.agent_id} size="lg" />
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-slate-100 truncate">
                {agent.agent_label || agent.agent_id}
              </h3>
              <StatusBadge status={agent.status || 'idle'} />
            </div>
            
            <p className="text-sm text-slate-500 font-mono mb-2">{agent.agent_id}</p>
            
            <div className="flex items-center gap-3 text-xs text-slate-400">
              {agent.last_active && (
                <span className="flex items-center gap-1">
                  <ClockIcon className="w-3 h-3" />
                  {formatTimeAgo(agent.last_active)}
                </span>
              )}
              {pendingCount > 0 && (
                <Badge variant="warning" dot>
                  {pendingCount} pending
                </Badge>
              )}
            </div>
          </div>
        </div>
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

function ClockIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}
