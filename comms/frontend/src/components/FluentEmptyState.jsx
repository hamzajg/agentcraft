import { FolderIcon } from './icons'

export function FluentEmptyState({ onFileClick }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-fluent-textTert p-8 animate-fade-in">
      {/* Decorative icon */}
      <div className="w-20 h-20 mb-6 rounded-fluent-xl bg-fluent-card border border-fluent-border flex items-center justify-center shadow-fluent-card">
        <svg className="w-10 h-10 text-fluent-textTert" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          <line x1="12" y1="11" x2="12" y2="17" />
          <line x1="9" y1="14" x2="15" y2="14" />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-fluent-textSec mb-2">AgentCraft Workspace</h2>
      <p className="text-sm text-fluent-textTert text-center max-w-md mb-6 leading-relaxed">
        Browse project files, communicate with agents, and monitor activity in real-time.
      </p>

      {/* File category chips */}
      <div className="flex items-center gap-3 text-xs mb-6">
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-fluent-accentSubtle text-fluent-accent">
          <span className="w-2 h-2 rounded-full bg-fluent-accent" />
          Documentation
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-fluent-warningBg text-fluent-warning">
          <span className="w-2 h-2 rounded-full bg-fluent-warning" />
          Workflow
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-fluent-success/10 text-fluent-success">
          <span className="w-2 h-2 rounded-full bg-fluent-success" />
          Generated Code
        </span>
      </div>

      {/* Quick action */}
      <button
        onClick={onFileClick}
        className="text-xs px-4 py-2 rounded-fluent-lg bg-fluent-card border border-fluent-border text-fluent-textSec hover:bg-fluent-cardHover hover:text-fluent-text transition-colors shadow-fluent-card"
      >
        Open File Explorer
      </button>
    </div>
  )
}
