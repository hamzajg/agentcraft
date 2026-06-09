import { useState, useEffect, useCallback } from 'react'
import { useHermesWebSocket } from './useHermesWebSocket'
import { api } from '../../lib/api'

// Extended api helper for Hermes-specific endpoints
const apiHermesMessage = async (text) => {
  const res = await fetch('/api/hermes/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export function useHermesData() {
  const [channels, setChannels] = useState([])
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState({})
  const [busMessages, setBusMessages] = useState([])
  const [buildState, setBuildState] = useState({
    status: 'idle',
    phase: 'Idle',
    progress: 0,
  })
  const [pendingMessages, setPendingMessages] = useState([])
  const [sending, setSending] = useState(false)

  // Fetch initial state
  const loadInitialData = useCallback(async () => {
    try {
      // Fetch active agent channels
      const channelData = await api.channels()
      setChannels(channelData || [])

      // Fetch pending clarifications
      const pendingData = await api.pending()
      if (pendingData && pendingData.messages) {
        setPendingMessages(pendingData.messages)
        
        // Populate statuses based on pending state
        const initialStatuses = {}
        channelData.forEach(ch => {
          initialStatuses[ch.agent_id] = 'idle'
        })
        pendingData.messages.forEach(m => {
          initialStatuses[m.agent_id] = 'blocked'
        })
        setStatuses(prev => ({ ...prev, ...initialStatuses }))
      }

      // Fetch recent bus messages
      try {
        const busData = await api.busMessages(100)
        setBusMessages(busData || [])
      } catch (e) {
        console.debug('Failed to load bus messages:', e)
      }

      // Fetch build state
      try {
        const bs = await api.buildState()
        if (bs) {
          let progress = 0
          if (bs.build_status === 'done') progress = 100
          else if (bs.build_status === 'running') {
            // Estimate progress based on current phase
            const phaseOrder = ['Spec', 'Architecture', 'SystemDesign', 'Coding', 'Testing', 'Verification']
            const idx = phaseOrder.indexOf(bs.current_phase)
            progress = idx >= 0 ? Math.round(((idx + 1) / phaseOrder.length) * 100) : 15
          }
          setBuildState({
            status: bs.build_status || 'idle',
            phase: bs.current_phase || 'Idle',
            progress: progress,
          })
        }
      } catch (e) {
        console.debug('Failed to load build state:', e)
      }
    } catch (err) {
      console.error('Failed to load initial Hermes data:', err)
    }
  }, [])

  // Setup WebSocket connection
  const handleWsMessage = useCallback((data) => {
    if (!data || !data.event) return

    switch (data.event) {
      case '_connected':
        loadInitialData()
        break

      case 'init':
        if (data.payload) {
          if (data.payload.channels) setChannels(data.payload.channels)
          if (data.payload.pending) {
            setPendingMessages(data.payload.pending)
            // Sync statuses
            setStatuses(prev => {
              const next = { ...prev }
              data.payload.pending.forEach(m => {
                next[m.agent_id] = 'blocked'
              })
              return next
            })
          }
        }
        break

      case 'clarification':
        if (data.payload) {
          const msg = data.payload
          const agentId = msg.agent_id

          // Add to messages cache for this agent
          setMessages(prev => {
            const list = prev[agentId] || []
            // Prevent duplicates
            if (list.some(m => m.id === msg.id)) return prev
            return {
              ...prev,
              [agentId]: [...list, msg]
            }
          })

          // Update status & pending list if message is pending
          if (msg.status === 'pending') {
            setStatuses(prev => ({ ...prev, [agentId]: 'blocked' }))
            setPendingMessages(prev => {
              if (prev.some(m => m.id === msg.id)) return prev
              return [...prev, msg]
            })
          }
        }
        break

      case 'reply_confirmed':
        if (data.payload) {
          const msg = data.payload
          const agentId = msg.agent_id

          // Update message in cache
          setMessages(prev => {
            const list = prev[agentId] || []
            return {
              ...prev,
              [agentId]: list.map(m => m.id === msg.id ? msg : m)
            }
          })

          // Remove from pending list
          setPendingMessages(prev => prev.filter(m => m.id !== msg.id))

          // Update agent status back to idle/running
          setStatuses(prev => ({ ...prev, [agentId]: 'idle' }))
        }
        break

      case 'agent_status':
        if (data.payload) {
          const { agent_id, status } = data.payload
          setStatuses(prev => ({ ...prev, [agent_id]: status }))
        }
        break

      case 'channels_updated':
        if (data.payload && data.payload.channels) {
          setChannels(data.payload.channels)
        }
        break

      case 'agents_built':
        // Handle build state / phases
        if (data.payload) {
          const p = data.payload
          setBuildState(prev => ({
            ...prev,
            status: p.status || prev.status,
            phase: p.phase || prev.phase,
            progress: p.progress || prev.progress,
          }))
        }
        break

      // Handle EventStream events forwarded by the backend
      case 'build_started':
        setBuildState({ status: 'running', phase: 'Spec', progress: 10 })
        break

      case 'build_done':
        setBuildState({ status: 'done', phase: 'Complete', progress: 100 })
        break

      case 'phase_changed':
        if (data.payload && data.payload.data) {
          const ph = data.payload.data.phase
          const phaseOrder = ['Spec', 'Architecture', 'SystemDesign', 'Coding', 'Testing', 'Verification']
          const idx = phaseOrder.indexOf(ph)
          const progress = idx >= 0 ? Math.round(((idx + 1) / phaseOrder.length) * 100) : 15
          setBuildState({ status: 'running', phase: ph, progress })
        }
        break

      default:
        break
    }
  }, [loadInitialData])

  const { isConnected } = useHermesWebSocket(handleWsMessage)

  // Fetch message history for a specific agent channel (if not cached)
  const fetchMessageHistory = useCallback(async (agentId) => {
    if (messages[agentId]) return messages[agentId]
    try {
      const history = await api.messages(agentId, 50)
      setMessages(prev => ({
        ...prev,
        [agentId]: history || []
      }))
      return history || []
    } catch (e) {
      console.error(`Failed to fetch messages for agent ${agentId}:`, e)
      return []
    }
  }, [messages])

  // Action: Send reply to a blocked agent
  const sendReply = useCallback(async (messageId, replyText) => {
    setSending(true)
    try {
      const res = await api.reply(messageId, replyText)
      setSending(false)
      return res
    } catch (err) {
      setSending(false)
      console.error('Failed to send reply:', err)
      throw err
    }
  }, [])

  // Action: Send direct prompt/message to Hermes
  const sendMessageToHermes = useCallback(async (text) => {
    setSending(true)
    try {
      const res = await apiHermesMessage(text)
      
      // Manually add the sent message locally to the 'hermes' channel history
      const userMsg = {
        id: `local-user-${Date.now()}`,
        agent_id: 'hermes',
        question: text,
        reply: text,
        created_at: new Date().toISOString(),
        status: 'replied'
      }

      setMessages(prev => {
        const list = prev['hermes'] || []
        return {
          ...prev,
          hermes: [...list, userMsg]
        }
      })

      setSending(false)
      return res
    } catch (err) {
      setSending(false)
      console.error('Failed to send message to Hermes:', err)
      throw err
    }
  }, [])

  // Calculate statistics
  const stats = {
    runningCount: Object.values(statuses).filter(s => s === 'active' || s === 'running').length,
    blockedCount: pendingMessages.length,
    idleCount: Object.values(statuses).filter(s => s === 'idle').length || channels.length - pendingMessages.length,
  }

  return {
    connected: isConnected,
    channels,
    statuses,
    messages,
    busMessages,
    buildState,
    pendingMessages,
    stats,
    sending,
    fetchMessageHistory,
    sendReply,
    sendMessageToHermes,
  }
}
