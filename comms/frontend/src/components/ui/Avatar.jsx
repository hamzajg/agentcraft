const colors = [
  'bg-accent',
  'bg-teal',
  'bg-amber',
  'bg-rose',
  'bg-violet',
  'bg-cyan',
]

function getInitials(name) {
  if (!name) return '?'
  const parts = name.split(/[_\s-]/).filter(Boolean)
  if (parts.length === 1) return parts[0][0].toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function getColor(name) {
  if (!name) return colors[0]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

export function Avatar({ name, size = 'md' }) {
  const sizes = {
    xs: 'w-4 h-4 text-[8px]',
    sm: 'w-6 h-6 text-[10px]',
    md: 'w-8 h-8 text-xs',
    lg: 'w-10 h-10 text-sm',
    xl: 'w-12 h-12 text-base',
  }

  return (
    <div
      className={`
        inline-flex items-center justify-center rounded-full
        font-semibold text-white
        ${sizes[size]}
        ${getColor(name)}
      `}
    >
      {getInitials(name)}
    </div>
  )
}
