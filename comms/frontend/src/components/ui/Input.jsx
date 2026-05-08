export function Input({ 
  className = '', 
  icon: Icon,
  ...props 
}) {
  return (
    <div className="relative">
      {Icon && (
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
          <Icon className="w-4 h-4" />
        </div>
      )}
      <input
        className={`
          w-full bg-slate-950 border border-slate-800 rounded-xl
          px-4 py-2.5 text-sm text-slate-100
          placeholder:text-slate-500
          focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20
          transition-colors
          ${Icon ? 'pl-10' : ''}
          ${className}
        `}
        {...props}
      />
    </div>
  )
}

export function Textarea({ className = '', ...props }) {
  return (
    <textarea
      className={`
        w-full bg-slate-950 border border-slate-800 rounded-xl
        px-4 py-3 text-sm text-slate-100
        placeholder:text-slate-500
        focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20
        transition-colors resize-none
        ${className}
      `}
      {...props}
    />
  )
}
