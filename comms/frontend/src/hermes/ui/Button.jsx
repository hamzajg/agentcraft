import React from 'react'

const variants = {
  primary: 'bg-hermes-gold hover:bg-amber-400 text-slate-950 font-bold border border-transparent shadow-lg shadow-amber-500/10 hover:shadow-amber-500/25 hermes-glow',
  secondary: 'bg-transparent text-cyan-400 border border-cyan-500/30 hover:border-cyan-400 hover:bg-cyan-500/10',
  gold: 'bg-transparent text-amber-400 border border-amber-500/30 hover:border-amber-400 hover:bg-amber-500/10',
  ghost: 'bg-transparent text-slate-300 hover:text-white hover:bg-slate-800/50',
  danger: 'bg-rose-500 hover:bg-rose-600 text-white font-semibold',
}

const sizes = {
  sm: 'px-3 py-1.5 text-xs rounded',
  md: 'px-4 py-2 text-sm rounded-md',
  lg: 'px-6 py-3 text-base rounded-lg',
}

export function Button({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  disabled = false,
  className = '', 
  onClick,
  type = 'button',
  ...props 
}) {
  return (
    <button
      type={type}
      className={`
        inline-flex items-center justify-center gap-2 font-semibold
        transition-all duration-200 active:scale-[0.98]
        disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
        ${variants[variant] || variants.primary}
        ${sizes[size] || sizes.md}
        ${className}
      `}
      onClick={onClick}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  )
}
