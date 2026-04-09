const variants = {
  default: 'bg-slate-800 text-slate-300',
  primary: 'bg-accent/20 text-accent border border-accent/30',
  success: 'bg-teal/20 text-teal border border-teal/30',
  warning: 'bg-amber/20 text-amber border border-amber/30',
  danger: 'bg-danger/20 text-danger border border-danger/30',
  muted: 'bg-slate-800/50 text-slate-500',
}

export function Badge({ children, variant = 'default', className = '', dot = false }) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium
        ${variants[variant]}
        ${className}
      `}
    >
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full bg-current animate-pulse`} />
      )}
      {children}
    </span>
  )
}
