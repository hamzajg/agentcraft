import { useState, useEffect, useCallback } from 'react'

export function useRagStats(pollInterval = 10_000) {
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const refresh = useCallback(async () => {
    try {
      const r = await fetch('/api/rag/stats')
      const d = await r.json()
      setStats(d)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, pollInterval)
    return () => clearInterval(t)
  }, [refresh, pollInterval])

  return { stats, loading, error, refresh }
}
