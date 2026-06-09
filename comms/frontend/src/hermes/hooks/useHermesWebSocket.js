import { useEffect, useRef, useState, useCallback } from 'react'

export function useHermesWebSocket(onMessage) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState(null)
  
  const ws = useRef(null)
  const timer = useRef(null)
  const cbRef = useRef(onMessage)
  
  // Keep callback ref updated
  useEffect(() => {
    cbRef.current = onMessage
  }, [onMessage])

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    // In dev, the Vite server proxies /ws to the backend, or we use current host
    const host = window.location.host
    const sock = new WebSocket(`${proto}://${host}/ws`)
    ws.current = sock

    sock.onopen = () => {
      setIsConnected(true)
      clearInterval(timer.current)
      
      const connEvent = { event: '_connected', data: { ts: Date.now() } }
      setLastEvent(connEvent)
      if (cbRef.current) cbRef.current(connEvent)

      // keepalive ping/pong
      timer.current = setInterval(() => {
        if (sock.readyState === WebSocket.OPEN) {
          sock.send('ping')
        }
      }, 25000)
    }

    sock.onmessage = (e) => {
      if (e.data === '{"event":"pong"}' || e.data === 'pong') return
      try {
        const data = JSON.parse(e.data)
        setLastEvent(data)
        if (cbRef.current) cbRef.current(data)
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err, e.data)
      }
    }

    sock.onclose = () => {
      setIsConnected(false)
      const disconnEvent = { event: '_disconnected', data: { ts: Date.now() } }
      setLastEvent(disconnEvent)
      if (cbRef.current) cbRef.current(disconnEvent)
      
      clearInterval(timer.current)
      // Retry connection after 2.5s
      setTimeout(connect, 2500)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearInterval(timer.current)
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [connect])

  const send = useCallback((data) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(typeof data === 'string' ? data : JSON.stringify(data))
      return true
    }
    return false
  }, [])

  return { isConnected, lastEvent, send }
}
