import { useEffect, useRef, useCallback } from 'react'

export function useWebSocket(onMessage) {
  const ws      = useRef(null)
  const timer   = useRef(null)
  const cbRef   = useRef(onMessage)
  cbRef.current = onMessage

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const sock  = new WebSocket(`${proto}://${location.host}/ws`)
    ws.current  = sock

    sock.onopen = () => {
      clearInterval(timer.current)
      cbRef.current({ event: '_connected' })
      // keepalive
      timer.current = setInterval(() => {
        if (sock.readyState === WebSocket.OPEN) sock.send('ping')
      }, 25_000)
    }

    sock.onmessage = (e) => {
      if (e.data === '{"event":"pong"}') return
      try { cbRef.current(JSON.parse(e.data)) } catch {}
    }

    sock.onclose = () => {
      cbRef.current({ event: '_disconnected' })
      clearInterval(timer.current)
      setTimeout(connect, 2_500)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearInterval(timer.current)
      ws.current?.close()
    }
  }, [connect])
}
