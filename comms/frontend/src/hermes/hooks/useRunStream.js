import { useEffect, useCallback, useRef } from 'react'
import { hermesApi } from '../lib/api'
import { useHermesRunStore } from '../stores/runStore'

export function useHermesRunStream(runId) {
  const { addEvent, clearEvents } = useHermesRunStore()
  const eventSourceRef = useRef(null)

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!runId) {
      disconnect()
      return
    }

    clearEvents()

    const eventSource = hermesApi.streamRun(runId)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        addEvent(data)
      } catch {
        // Ignore parse errors (heartbeats, etc.)
      }
    }

    eventSource.onerror = () => {
      console.error('Hermes SSE connection error')
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [runId, addEvent, clearEvents, disconnect])

  return { disconnect }
}
