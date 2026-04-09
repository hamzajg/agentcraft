import { StatusDot } from '../ui'

export function Header({ connected, pendingCount, agentCount, onLogoClick }) {
  return (
    <header className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onLogoClick} className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-violet-600 flex items-center justify-center">
              <RobotIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-slate-100">AgentCraft</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent font-medium">v2</span>
          </button>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <StatusDot status={connected ? 'running' : 'idle'} pulse={connected} />
              <span className="text-slate-400">{connected ? 'Connected' : 'Disconnected'}</span>
            </div>

            <div className="w-px h-4 bg-slate-800" />

            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-slate-800 flex items-center justify-center">
                <AgentIcon className="w-3 h-3 text-slate-400" />
              </div>
              <span className="text-slate-300">{agentCount} agents</span>
            </div>

            {pendingCount > 0 && (
              <>
                <div className="w-px h-4 bg-slate-800" />
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <div className="w-5 h-5 rounded bg-amber/20 flex items-center justify-center">
                      <BellIcon className="w-3 h-3 text-amber" />
                    </div>
                    <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber text-[10px] font-bold text-slate-950 flex items-center justify-center">
                      {pendingCount > 9 ? '9+' : pendingCount}
                    </span>
                  </div>
                  <span className="text-amber font-medium">{pendingCount} pending</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

function RobotIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  )
}

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

function BellIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}
