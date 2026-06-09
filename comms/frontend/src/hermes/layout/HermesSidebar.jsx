import React from 'react'
import { NavLink } from 'react-router-dom'
import { 
  BriefcaseIcon, 
  UsersIcon, 
  BookOpenIcon, 
  ChartIcon, 
  WifiIcon
} from '../../components/icons'

export function HermesSidebar({ stats = null }) {
  const navItems = [
    { to: '/hermes/workspace', label: 'Workspace', icon: BriefcaseIcon },
    { to: '/hermes/agents', label: 'Agents', icon: UsersIcon },
    { to: '/hermes/rag', label: 'RAG Knowledge', icon: BookOpenIcon },
    { to: '/hermes/monitor', label: 'Monitor', icon: ChartIcon },
    { to: '/hermes/events', label: 'Events Bus', icon: WifiIcon },
  ]

  return (
    <aside 
      className="fixed top-16 left-0 bottom-0 w-16 hover:w-48 bg-[#0c1220]/95 backdrop-blur-md border-r border-slate-800/80 z-40 transition-all duration-300 group flex flex-col justify-between overflow-x-hidden select-none"
    >
      {/* Navigation links */}
      <nav className="pt-4 flex-1 flex flex-col gap-1.5 px-2">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `
                flex items-center gap-4 px-3 py-3 rounded-md text-sm font-semibold transition-all duration-200 relative
                ${isActive 
                  ? 'text-amber-400 bg-amber-500/5' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/40'}
              `}
            >
              {({ isActive }) => (
                <>
                  {/* Left indicator strip */}
                  {isActive && (
                    <span className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-amber-500 rounded-r" />
                  )}
                  <Icon className="w-5 h-5 min-w-[20px] transition-transform duration-200 group-hover:scale-105" />
                  <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 font-sans tracking-wide whitespace-nowrap">
                    {item.label}
                  </span>
                </>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Roster stats summary at the bottom */}
      {stats && (
        <div className="p-3 border-t border-slate-900 bg-[#090d16]/40 flex flex-col gap-2 font-mono text-[10px]">
          {/* Collapsed view (small dot indicators) */}
          <div className="flex flex-col gap-1.5 items-center group-hover:hidden py-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" title={`${stats.runningCount || 0} active`} />
            <span className="w-2 h-2 rounded-full bg-amber-500" title={`${stats.blockedCount || 0} pending`} />
            <span className="w-2 h-2 rounded-full bg-slate-500" title={`${stats.idleCount || 0} idle`} />
          </div>

          {/* Expanded view */}
          <div className="hidden group-hover:flex flex-col gap-1 text-slate-400">
            <div className="flex justify-between items-center">
              <span>Active</span>
              <span className="text-emerald-400 font-bold">{stats.runningCount || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span>Pending</span>
              <span className="text-amber-400 font-bold">{stats.blockedCount || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span>Idle</span>
              <span className="text-slate-500 font-bold">{stats.idleCount || 0}</span>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
