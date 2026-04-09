import { useNavigate, useLocation } from 'react-router-dom'
import { StatusDot } from './ui'

const ROUTES = [
  { path: '/classic/', label: 'Dashboard', icon: DashboardIcon },
  { path: '/classic/chat', label: 'Chat', icon: ChatIcon },
  { path: '/classic/agents', label: 'Agents', icon: AgentsIcon },
  { path: '/classic/tasks', label: 'Tasks', icon: TasksIcon },
  { path: '/classic/activity', label: 'Activity', icon: ActivityIcon },
]

export function ClassicLayout({ children, channels, statuses, messages, events, activeAgent, setActiveAgent, connected, pendingCount, sending, onReply }) {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div className="h-screen flex flex-col bg-slate-950 overflow-hidden">
      {/* Header */}
      <header className="h-12 flex-shrink-0 bg-slate-900 border-b border-slate-800 flex items-center px-4 gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-accent/20 border border-accent/30 flex items-center justify-center">
            <TerminalIcon />
          </div>
          <span className="font-semibold text-sm tracking-tight">AgentCraft</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">Classic</span>
        </div>

        <div className="flex items-center gap-1.5">
          <StatusDot status={connected ? 'running' : 'idle'} />
          <span className="text-[11px] text-slate-500">{connected ? 'connected' : 'reconnecting…'}</span>
        </div>

        <div className="flex-1" />

        {pendingCount > 0 && (
          <div className="flex items-center gap-1.5 bg-amber/10 border border-amber/30 rounded-full px-3 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
            <span className="text-xs text-amber font-medium">
              {pendingCount} waiting {pendingCount === 1 ? 'reply' : 'replies'}
            </span>
          </div>
        )}
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-48 flex-shrink-0 border-r border-slate-800 bg-slate-950 overflow-y-auto">
          <nav className="p-3 space-y-1">
            {ROUTES.map((route) => {
              const isActive = location.pathname === route.path || 
                (route.path !== '/classic/' && location.pathname.startsWith(route.path))
              return (
                <button
                  key={route.path}
                  onClick={() => navigate(route.path)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                    ${isActive 
                      ? 'bg-accent/20 text-accent font-medium' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }
                  `}
                >
                  <route.icon />
                  {route.label}
                  {route.path === '/classic/chat' && pendingCount > 0 && (
                    <span className="ml-auto w-5 h-5 rounded-full bg-amber text-black text-xs font-bold flex items-center justify-center">
                      {pendingCount > 9 ? '9+' : pendingCount}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>

          {/* Agent list */}
          <div className="p-3 border-t border-slate-800">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2 px-3">Agents</p>
            <div className="space-y-1">
              {channels.length === 0 ? (
                <p className="text-xs text-slate-600 px-3 py-2">No agents connected</p>
              ) : (
                channels.map((channel) => (
                  <button
                    key={channel.agent_id}
                    onClick={() => {
                      navigate('/classic/chat')
                      setActiveAgent(channel.agent_id)
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors
                      ${activeAgent === channel.agent_id 
                        ? 'bg-accent/10 text-accent' 
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
                      }
                    `}
                  >
                    <StatusDot status={statuses[channel.agent_id] || 'idle'} size="sm" />
                    <span className="truncate">{channel.agent_label || channel.agent_id}</span>
                    {channel.unread > 0 && (
                      <span className="ml-auto w-4 h-4 rounded-full bg-accent text-white text-[10px] font-bold flex items-center justify-center">
                        {channel.unread}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}

function TerminalIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-accent" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 4l4 4-4 4M8 12h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function DashboardIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function AgentsIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}

function TasksIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  )
}

function ActivityIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}
