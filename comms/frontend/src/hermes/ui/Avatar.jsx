import React from 'react'

const colors = [
  'bg-amber-600/30 text-amber-300 border border-amber-500/30',
  'bg-cyan-600/30 text-cyan-300 border border-cyan-500/30',
  'bg-emerald-600/30 text-emerald-300 border border-emerald-500/30',
  'bg-violet-600/30 text-violet-300 border border-violet-500/30',
  'bg-rose-600/30 text-rose-300 border border-rose-500/30',
  'bg-sky-600/30 text-sky-300 border border-sky-500/30',
]

function getInitials(name) {
  if (!name) return '?'
  if (name.toLowerCase() === 'hermes') return 'H'
  const parts = name.split(/[_\s-]/).filter(Boolean)
  if (parts.length === 1) return parts[0][0].toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function getColor(name) {
  if (!name) return colors[0]
  if (name.toLowerCase() === 'hermes') return 'bg-amber-500/20 text-amber-400 border border-amber-500/60 shadow-lg shadow-amber-500/10'
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

export function Avatar({ name, size = 'md', status = null }) {
  const sizes = {
    xs: 'w-5 h-5 text-[9px]',
    sm: 'w-7 h-7 text-[11px]',
    md: 'w-9 h-9 text-xs',
    lg: 'w-11 h-11 text-sm',
    xl: 'w-14 h-14 text-base',
  }

  const isHermes = name?.toLowerCase() === 'hermes'

  return (
    <div className="relative inline-block">
      <div
        className={`
          inline-flex items-center justify-center rounded-full
          font-bold select-none transition-all duration-300
          ${sizes[size] || sizes.md}
          ${getColor(name)}
        `}
      >
        {isHermes ? (
          // Mini Winged Caduceus SVG for Hermes agent avatar
          <svg className="w-5 h-5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v20M17 5H7M18 9H6" />
            <path d="M12 4a4 4 0 0 0-4 4 4 4 0 0 0 4 4 4 4 0 0 0 4-4 4 4 0 0 0-4-4Z" />
            <path d="M12 11c-2 0-3 1.5-3 3s1 3 3 3 3-1.5 3-3-1-3-3-3Z" />
            <path d="M5 9c-2 0-3-1.5-3-3s1.5-3 3-3c2.5 0 4.5 4 4 6" />
            <path d="M19 9c2 0 3-1.5 3-3s-1.5-3-3-3c-2.5 0-4.5 4-4 6" />
          </svg>
        ) : (
          getInitials(name)
        )}
      </div>
      {status && (
        <span 
          className={`
            absolute bottom-0 right-0 block w-2.5 h-2.5 rounded-full ring-2 ring-slate-950
            ${status === 'active' || status === 'running' ? 'bg-emerald-400' : ''}
            ${status === 'blocked' || status === 'pending' ? 'bg-amber-400 animate-pulse' : ''}
            ${status === 'idle' ? 'bg-slate-500' : ''}
          `}
        />
      )}
    </div>
  )
}
