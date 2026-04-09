export function Card({ children, className = '', hover = false, ...props }) {
  return (
    <div
      className={`
        bg-slate-900 border border-slate-800 rounded-xl
        ${hover ? 'hover:border-slate-700 hover:bg-slate-900/80 transition-colors cursor-pointer' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`px-5 py-4 border-b border-slate-800 ${className}`}>
      {children}
    </div>
  )
}

export function CardBody({ children, className = '' }) {
  return (
    <div className={`p-5 ${className}`}>
      {children}
    </div>
  )
}
