import React from 'react'

const variants = {
  default: 'bg-slate-800 text-slate-300 border border-slate-700/50',
  gold: 'bg-amber-500/10 text-amber-400 border border-amber-500/30 shadow-sm shadow-amber-500/5',
  cyan: 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/5',
  success: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30',
  warning: 'bg-orange-500/10 text-orange-400 border border-orange-500/30',
  danger: 'bg-rose-500/10 text-rose-400 border border-rose-500/30',
  muted: 'bg-slate-900/50 text-slate-500 border border-slate-800/20',
}

export function Badge({ children, variant = 'default', className = '', dot = false }) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold tracking-wide
        ${variants[variant] || variants.default}
        ${className}
      `}
    >
      {dot && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {children}
    </span>
  )
}
