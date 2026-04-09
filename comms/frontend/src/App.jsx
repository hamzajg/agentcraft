import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useWebSocket } from './hooks/useWebSocket'
import { api } from './lib/api'
import { WorkspaceLayout, ClassicLayout } from './v2/components'
import { Dashboard, Chat, Agents, Tasks, Activity } from './v2/pages'
import { MonitorPage } from './pages/MonitorPage'
import { RagPage } from './pages/RagPage'
import { BusPage } from './pages/BusPage'
import { LivePage } from './pages/LivePage'
import { ConsolePage } from './pages/ConsolePage'

function AppLayout({ children }) {
  return <>{children}</>
}

export default function App() {
  const [channels, setChannels] = useState([])
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState({})
  const [pendingCount, setPendingCount] = useState(0)
  const [activeAgent, setActiveAgent] = useState(null)
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const [sending, setSending] = useState(false)
  const [logs, setLogs] = useState([])

  const handleWsEvent = useCallback((ev) => {
    const { event, payload } = ev
    
    if (event === '_connected') { setConnected(true); return }
    if (event === '_disconnected') { setConnected(false); return }

    if (event === 'clarification' || event === 'agent_reply') {
      const m = payload

      setMessages((prev) => {
        const list = prev[m.agent_id] ?? []
        const idx = list.findIndex((x) => x.id === m.id)
        return { ...prev, [m.agent_id]: idx >= 0 ? [...list.slice(0, idx), m, ...list.slice(idx + 1)] : [...list, m] }
      })
      setPendingCount((n) => Math.max(0, n + (event === 'clarification' ? 1 : 0) - (event === 'agent_reply' ? 1 : 0)))
      if (!activeAgent) setActiveAgent(payload.agent_id)
      const id = payload.id || payload.message_id || crypto.randomUUID()
      setEvents((prev) => [{ id, type: event, agent_id: payload.agent_id, text: payload.question || payload.content, time: new Date().toISOString() }, ...prev].slice(0, 100))
      
      if (event === 'clarification') {
        const prevTitle = document.title
        document.title = `(${payload.agent_label || payload.agent_id}) needs input — AgentCraft`
        setTimeout(() => { document.title = prevTitle }, 6000)
      }
      return
    }

    if (event === 'channels_updated') {
      if (payload.channels) {
        setChannels(payload.channels)
        // Set active agent if none selected
        if (!activeAgent && payload.channels.length > 0) {
          setActiveAgent(payload.channels[0].agent_id)
        }
      }
      return
    }

    if (event === 'reply_confirmed') {
      if (payload.agent_id && payload.id) {
        setMessages((prev) => {
          const list = prev[payload.agent_id] ?? []
          const idx = list.findIndex((x) => x.id === payload.id)
          if (idx >= 0) {
            const updated = [...list]
            updated[idx] = { ...updated[idx], ...payload, status: 'replied' }
            return { ...prev, [payload.agent_id]: updated }
          }
          return prev
        })
      }
      return
    }

    if (event === 'agent_status') {
      setStatuses((prev) => ({ ...prev, [payload.agent_id]: payload.status }))
      const id = payload.id || crypto.randomUUID()
      setEvents((prev) => [{ id, type: event, agent_id: payload.agent_id, text: `${payload.agent_id} is ${payload.status}`, time: new Date().toISOString() }, ...prev].slice(0, 100))
      return
    }

    if (event === 'agent_broadcast') {
      const id = payload.id || crypto.randomUUID()
      setEvents((prev) => [{ id, type: event, agent_id: payload.agent_id, text: `Broadcast: ${payload.content?.event ?? 'update'}`, time: new Date().toISOString() }, ...prev].slice(0, 100))
      return
    }

    if (event === 'log') {
      const id = payload.id || crypto.randomUUID()
      setEvents((prev) => [{ id, type: event, agent_id: payload.agent_id, text: payload.message?.slice(0, 120) || 'Log entry', time: new Date().toISOString() }, ...prev].slice(0, 100))
      setLogs((prev) => [...prev, payload])
      return
    }

    if (event.includes('task') || event.includes('phase') || event.includes('iter') || event.includes('build')) {
      const id = payload.id || crypto.randomUUID()
      setEvents((prev) => [{ id, type: event, agent_id: payload.agent_id, text: payload.text || payload.content || event, time: new Date().toISOString() }, ...prev].slice(0, 100))
    }
  }, [activeAgent])

  useWebSocket(handleWsEvent)

  const loadStatus = useCallback(async () => {
    try {
      const [channelsData, pending] = await Promise.all([
        api.channels().catch(() => []),
        api.pending().catch(() => ({ messages: [] })),
      ])
      setChannels(channelsData)
      setPendingCount(pending.messages?.length || 0)
      const newPendingMessages = {}
      pending.messages?.forEach((m) => {
        newPendingMessages[m.agent_id] = [...(newPendingMessages[m.agent_id] || []), m]
      })
      // Merge with existing messages, preserving existing messages
      setMessages((prev) => ({ ...prev, ...newPendingMessages }))
      if (!activeAgent && channelsData.length > 0) {
        setActiveAgent(channelsData[0].agent_id)
      }
    } catch (error) {
      console.error('Failed to load status', error)
    }
  }, [activeAgent])

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 30000)
    return () => clearInterval(interval)
  }, [loadStatus])

  useEffect(() => {
    if (!activeAgent || messages[activeAgent]?.length > 0) return
    api.messages(activeAgent)
      .then(msgs => setMessages(prev => ({ ...prev, [activeAgent]: msgs })))
      .catch(() => {})
  }, [activeAgent])

  const handleReply = async (msgId, text) => {
    if (sending) return
    setSending(true)
    try {
      const result = await api.reply(msgId, text)
      // Update the message in local state with the confirmed reply
      if (result?.message) {
        const confirmedMsg = result.message
        setMessages((prev) => {
          const list = prev[confirmedMsg.agent_id] ?? []
          const idx = list.findIndex((x) => x.id === confirmedMsg.id)
          if (idx >= 0) {
            const updated = [...list]
            updated[idx] = confirmedMsg
            return { ...prev, [confirmedMsg.agent_id]: updated }
          }
          // Message not in list, add it
          return { ...prev, [confirmedMsg.agent_id]: [confirmedMsg, ...list] }
        })
      }
      // Also refresh pending count
      loadStatus()
    } catch (e) {
      console.error('reply failed', e)
    } finally {
      setSending(false)
    }
  }

  const pageProps = {
    channels,
    statuses,
    messages,
    events,
    activeAgent,
    setActiveAgent,
    pendingCount,
    sending,
    onReply: handleReply,
    onRefresh: loadStatus,
  }

  return (
    <Routes>
      {/* NEW: Workspace Layout (Default) - 3-pane workspace tool */}
      <Route path="/" element={
        <WorkspaceLayout
          channels={channels}
          statuses={statuses}
          messages={messages}
          events={events}
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
          connected={connected}
          pendingCount={pendingCount}
          sending={sending}
          setSending={setSending}
          onReply={handleReply}
          onRefresh={loadStatus}
        />
      } />

      {/* CLASSIC: Old tab-based layout */}
      <Route path="/classic" element={
        <ClassicLayout
          channels={channels}
          statuses={statuses}
          messages={messages}
          events={events}
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
          connected={connected}
          pendingCount={pendingCount}
        >
          <Outlet />
        </ClassicLayout>
      }>
        <Route index element={<Dashboard {...pageProps} />} />
        <Route path="chat" element={<Chat {...pageProps} />} />
        <Route path="agents" element={<Agents {...pageProps} />} />
        <Route path="tasks" element={<Tasks {...pageProps} />} />
        <Route path="activity" element={<Activity {...pageProps} />} />
      </Route>

      {/* LEGACY: Other pages */}
      <Route path="/monitor" element={<MonitorPage />} />
      <Route path="/rag" element={<RagPage />} />
      <Route path="/bus" element={<BusPage />} />
      <Route path="/live" element={<LivePage />} />
      <Route path="/console" element={<ConsolePage logs={logs} />} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
