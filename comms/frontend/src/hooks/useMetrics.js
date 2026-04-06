import { useState, useEffect, useRef } from 'react'

const HISTORY_LEN = 60   // keep 60 data points (~2 min at 2s interval)

export function useMetrics() {
  const [latest,  setLatest]  = useState(null)
  const [history, setHistory] = useState([])   // array of SystemMetrics snapshots
  const [error,   setError]   = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    const es = new EventSource('/api/metrics')
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const m = JSON.parse(e.data)
        if (m.error) { setError(m.error); return }
        setError(null)
        setLatest(m)
        setHistory(prev => {
          const next = [...prev, m]
          return next.length > HISTORY_LEN ? next.slice(-HISTORY_LEN) : next
        })
      } catch {}
    }

    es.onerror = () => setError('Metrics stream disconnected — retrying…')

    return () => { es.close() }
  }, [])

  return { latest, history, error }
}
