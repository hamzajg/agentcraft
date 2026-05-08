import { BriefcaseIcon, BookOpenIcon, ChartIcon, WifiIcon, FolderIcon, HammerIcon, RocketIcon } from './icons'

export function TopBar({ 
  connected, 
  pendingCount, 
  agentCount, 
  statuses, 
  buildState, 
  activeTab, 
  onTabChange, 
  onToggleLeftPanel, 
  leftPanelCollapsed, 
  hasBuildReport, 
  showBuildPanel, 
  onToggleBuildPanel 
}) {
  const tabs = [
    { id: 'workspace', label: 'Workspace', icon: BriefcaseIcon },
    { id: 'rag', label: 'RAG', icon: BookOpenIcon },
    { id: 'monitor', label: 'Monitor', icon: ChartIcon },
    { id: 'events', label: 'Events Bus', icon: WifiIcon },
  ]

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16" style={{ background: 'rgba(12, 18, 32, 0.95)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(100, 180, 255, 0.12)' }}>
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 flex items-center justify-center" style={{ color: 'var(--accent-primary)' }}>
            <RocketIcon className="w-6 h-6" />
          </div>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>AgentCraft</div>
        </div>

        {/* Toolbox Tab Bar */}
        <nav className="flex items-center p-1 rounded-lg" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all duration-200"
                style={{
                  color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: activeTab === tab.id ? 'var(--bg-tertiary)' : 'transparent',
                }}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>

        {/* Status */}
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2" style={{ color: connected ? 'var(--accent-primary)' : 'var(--text-tertiary)' }}>
            <span>{connected ? '●' : '○'}</span>
            <span>{connected ? 'Connected' : 'Offline'}</span>
          </div>

          {buildState && (
            <div className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
              <span>{buildState.status || 'Building'}</span>
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--success)' }} />
            </div>
          )}

          {pendingCount > 0 && (
            <button className="flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium" style={{ background: 'var(--accent-primary)', color: 'var(--bg-primary)' }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--bg-primary)' }} />
              <span>{pendingCount}</span>
            </button>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleLeftPanel}
            className="px-3 py-2 rounded"
            style={{ color: 'var(--text-secondary)' }}
            title={leftPanelCollapsed ? 'Expand file explorer' : 'Collapse file explorer'}
          >
            <FolderIcon className="w-5 h-5" />
          </button>

          {hasBuildReport && (
            <button
              onClick={onToggleBuildPanel}
              className="px-3 py-2 rounded"
              style={{ color: showBuildPanel ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
              title={showBuildPanel ? 'Hide build panel' : 'Show build panel'}
            >
              <HammerIcon className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
