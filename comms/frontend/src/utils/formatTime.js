export function formatTime(isoString) {
  if (!isoString) return '--:--:--'
  try {
    return new Date(isoString).toLocaleTimeString()
  } catch {
    return isoString
  }
}

export function formatDate(isoString) {
  if (!isoString) return '--/--/--'
  try {
    return new Date(isoString).toLocaleDateString()
  } catch {
    return isoString
  }
}

export function formatRelativeTime(isoString) {
  if (!isoString) return 'unknown'
  
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diff = now - date
    
    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)
    
    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'just now'
  } catch {
    return isoString
  }
}
