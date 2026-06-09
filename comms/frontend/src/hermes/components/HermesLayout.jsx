import { useState, useEffect, useCallback } from 'react'
import AgentSidebar from './AgentSidebar'
import ChatArea from './ChatArea'
import ArtifactsPanel from './ArtifactsPanel'
import AgentsFactoryPage from '../pages/AgentsFactoryPage'
import SkillsPage from '../pages/SkillsPage'
import ToolsPage from '../pages/ToolsPage'
import RunsPage from '../pages/RunsPage'
import { hermesApi } from '../lib/api'

const NAV_ITEMS = [
  { id: 'agents', label: 'Agents', icon: '&#129302;' },
  { id: 'chat', label: 'Chat', icon: '&#128172;' },
  { id: 'skills', label: 'Skills', icon: '&#129504;' },
  { id: 'tools', label: 'Tools', icon: '&#128295;' },
  { id: 'runs', label: 'Runs', icon: '&#9654;' },
]

export default function HermesLayout() {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [conversations, setConversations] = useState([])
  const [selectedConv, setSelectedConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [artifacts, setArtifacts] = useState([])
  const [memories, setMemories] = useState([])
  const [skills, setSkills] = useState([])
  const [showArtifacts, setShowArtifacts] = useState(false)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState('agents')

  useEffect(() => {
    const load = async () => {
      try {
        const [agentsData, skillsData] = await Promise.all([
          hermesApi.listAgents(),
          hermesApi.listSkills(),
        ])
        setAgents(agentsData)
        setSkills(skillsData)
        if (agentsData.length > 0) setSelectedAgent(agentsData[0])
      } catch (e) {
        console.error('Failed to load initial data:', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!selectedAgent) return
    const loadConvs = async () => {
      try {
        const convs = await hermesApi.listConversations(selectedAgent.id)
        setConversations(convs)
        if (convs.length > 0 && !selectedConv) setSelectedConv(convs[0])
      } catch (e) { console.error('Failed to load conversations:', e) }
    }
    loadConvs()
  }, [selectedAgent?.id])

  useEffect(() => {
    if (!selectedConv) { setMessages([]); return }
    const loadMsgs = async () => {
      try {
        const msgs = await hermesApi.listMessages(selectedConv.id)
        setMessages(msgs)
      } catch (e) { console.error('Failed to load messages:', e) }
    }
    loadMsgs()
  }, [selectedConv?.id])

  useEffect(() => {
    if (!selectedAgent) { setArtifacts([]); return }
    const loadArtifacts = async () => {
      try {
        const arts = await hermesApi.listArtifacts(selectedAgent.id)
        setArtifacts(arts)
      } catch (e) { console.error('Failed to load artifacts:', e) }
    }
    loadArtifacts()
  }, [selectedAgent?.id])

  const handleNewConversation = useCallback(async () => {
    if (!selectedAgent) return
    try {
      const conv = await hermesApi.createConversation(selectedAgent.id, { title: 'New conversation' })
      setConversations(prev => [conv, ...prev])
      setSelectedConv(conv)
    } catch (e) { console.error('Failed to create conversation:', e) }
  }, [selectedAgent?.id])

  const handleSendMessage = useCallback(async (content) => {
    if (!selectedConv) return
    const userMsg = {
      id: crypto.randomUUID(), conversation_id: selectedConv.id,
      message_type: 'user', content, created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    try {
      await hermesApi.sendMessage(selectedConv.id, content)
      setTimeout(async () => {
        try {
          const msgs = await hermesApi.listMessages(selectedConv.id)
          setMessages(msgs)
        } catch (e) { /* ignore */ }
      }, 1000)
    } catch (e) { console.error('Failed to send message:', e) }
  }, [selectedConv?.id])

  const handleSelectAgent = useCallback((agent) => {
    setSelectedAgent(agent)
    setSelectedConv(null)
    setMessages([])
    setPage('chat')
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--text-secondary)' }}>
        Loading Hermes...
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>
      {/* Left Nav Rail */}
      <div style={{
        width: 56, minWidth: 56, height: '100%',
        background: '#080e18', borderRight: '1px solid var(--border-subtle)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 0',
        gap: 4,
      }}>
        {/* Hermes Logo */}
        <div style={{
          width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg, var(--accent-primary), #0088cc)', marginBottom: 12,
          fontSize: 16, fontWeight: 700, color: '#fff',
        }}>H</div>

        {/* Nav Items */}
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            onClick={() => setPage(item.id)}
            title={item.label}
            style={{
              width: 40, height: 40, borderRadius: 8, border: 'none', cursor: 'pointer',
              background: page === item.id ? 'var(--accent-dim)' : 'transparent',
              color: page === item.id ? 'var(--accent-primary)' : 'var(--text-tertiary)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 2, fontSize: 16, transition: 'all 0.15s',
            }}
          >
            <span dangerouslySetInnerHTML={{ __html: item.icon }} />
            <span style={{ fontSize: 8, fontWeight: 500 }}>{item.label}</span>
          </button>
        ))}
      </div>

      {/* Main Content */}
      {page === 'chat' ? (
        <>
          <AgentSidebar
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={handleSelectAgent}
            conversations={conversations}
            selectedConv={selectedConv}
            onSelectConv={setSelectedConv}
            onNewConversation={handleNewConversation}
            skills={skills}
            memories={memories}
          />
          <ChatArea
            agent={selectedAgent}
            conversation={selectedConv}
            messages={messages}
            onSendMessage={handleSendMessage}
            onToggleArtifacts={() => setShowArtifacts(!showArtifacts)}
            showArtifacts={showArtifacts}
            artifactCount={artifacts.length}
          />
          {showArtifacts && (
            <ArtifactsPanel
              agent={selectedAgent}
              artifacts={artifacts}
              onClose={() => setShowArtifacts(false)}
            />
          )}
        </>
      ) : page === 'agents' ? (
        <div style={{ flex: 1, overflow: 'hidden' }}><AgentsFactoryPage onAgentCreated={(agent) => { setAgents(prev => [...prev, agent]); setSelectedAgent(agent); setPage('chat') }} /></div>
      ) : page === 'skills' ? (
        <div style={{ flex: 1, overflow: 'hidden' }}><SkillsPage /></div>
      ) : page === 'tools' ? (
        <div style={{ flex: 1, overflow: 'hidden' }}><ToolsPage /></div>
      ) : page === 'runs' ? (
        <div style={{ flex: 1, overflow: 'hidden' }}><RunsPage /></div>
      ) : null}
    </div>
  )
}
