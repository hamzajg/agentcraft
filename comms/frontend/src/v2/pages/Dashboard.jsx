import { Card, CardBody, Badge, Button } from '../components/ui'
import { StatCard } from '../components/StatCard'
import { EventFeed } from '../components/EventFeed'

export function Dashboard({ channels, statuses, pendingCount, events, connected, onNavigate }) {
  const runningAgents = Object.values(statuses).filter(s => s === 'running').length
  const idleAgents = channels.length - runningAgents

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">Overview of your autonomous agent workspace</p>
        </div>
        <Button onClick={onRefresh} variant="secondary" size="sm">
          <RefreshIcon className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Active Agents"
          value={runningAgents}
          subtitle={`${channels.length} total`}
          icon={AgentIcon}
          variant="success"
        />
        <StatCard
          title="Pending Actions"
          value={pendingCount}
          subtitle={pendingCount > 0 ? 'Needs attention' : 'All clear'}
          icon={PendingIcon}
          variant={pendingCount > 0 ? 'warning' : 'default'}
        />
        <StatCard
          title="Events Today"
          value={events.length}
          subtitle="Real-time activity"
          icon={ActivityIcon}
        />
        <StatCard
          title="Connection"
          value={connected ? 'Online' : 'Offline'}
          subtitle={connected ? 'WebSocket active' : 'Reconnecting...'}
          icon={connected ? ConnectedIcon : DisconnectedIcon}
          variant={connected ? 'success' : 'danger'}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardBody className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-100">Agent Status</h2>
              <Badge variant="muted">{channels.length} channels</Badge>
            </div>
            <div className="space-y-3">
              {channels.length === 0 ? (
                <div className="text-center py-8">
                  <div className="w-12 h-12 rounded-xl bg-slate-800 mx-auto mb-3 flex items-center justify-center">
                    <AgentIcon className="w-6 h-6 text-slate-600" />
                  </div>
                  <p className="text-sm text-slate-500">No agents connected</p>
                  <p className="text-xs text-slate-600 mt-1">Start a session to see agents here</p>
                </div>
              ) : (
                channels.map((channel) => (
                  <div 
                    key={channel.agent_id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 transition-colors cursor-pointer"
                    onClick={() => onNavigate('/chat')}
                  >
                    <div className={`w-2 h-2 rounded-full ${statuses[channel.agent_id] === 'running' ? 'bg-teal' : 'bg-slate-500'}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-200 truncate">
                        {channel.agent_label || channel.agent_id}
                      </p>
                      <p className="text-xs text-slate-500 font-mono">{channel.agent_id}</p>
                    </div>
                    <span className={`text-xs ${statuses[channel.agent_id] === 'running' ? 'text-teal' : 'text-slate-500'}`}>
                      {statuses[channel.agent_id] || 'idle'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </CardBody>
        </Card>

        <EventFeed events={events} maxHeight="300px" />
      </div>

      <Card>
        <CardBody className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-100">Quick Actions</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <button 
              onClick={() => onNavigate('/chat')}
              className="flex items-center gap-3 p-4 rounded-xl border border-slate-800 hover:border-accent/50 hover:bg-accent/5 transition-all text-left"
            >
              <div className="w-10 h-10 rounded-lg bg-accent/20 flex items-center justify-center">
                <ChatIcon className="w-5 h-5 text-accent" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-200">Open Chat</p>
                <p className="text-xs text-slate-500">Collaborate with agents</p>
              </div>
            </button>

            <button 
              onClick={() => onNavigate('/agents')}
              className="flex items-center gap-3 p-4 rounded-xl border border-slate-800 hover:border-teal/50 hover:bg-teal/5 transition-all text-left"
            >
              <div className="w-10 h-10 rounded-lg bg-teal/20 flex items-center justify-center">
                <AgentIcon className="w-5 h-5 text-teal" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-200">View Agents</p>
                <p className="text-xs text-slate-500">Manage agent roster</p>
              </div>
            </button>

            <button 
              onClick={() => onNavigate('/tasks')}
              className="flex items-center gap-3 p-4 rounded-xl border border-slate-800 hover:border-amber/50 hover:bg-amber/5 transition-all text-left"
            >
              <div className="w-10 h-10 rounded-lg bg-amber/20 flex items-center justify-center">
                <TaskIcon className="w-5 h-5 text-amber" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-200">View Tasks</p>
                <p className="text-xs text-slate-500">Track progress</p>
              </div>
            </button>

            <button 
              onClick={() => onNavigate('/workspace')}
              className="flex items-center gap-3 p-4 rounded-xl border border-slate-800 hover:border-slate-700 hover:bg-slate-800/30 transition-all text-left"
            >
              <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center">
                <WorkspaceIcon className="w-5 h-5 text-slate-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-200">Workspace</p>
                <p className="text-xs text-slate-500">Files & context</p>
              </div>
            </button>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

const onRefresh = () => window.location.reload()

function AgentIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}

function PendingIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function ActivityIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}

function ConnectedIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" />
    </svg>
  )
}

function DisconnectedIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
      <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
      <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
      <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" />
    </svg>
  )
}

function ChatIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
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

function WorkspaceIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
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
