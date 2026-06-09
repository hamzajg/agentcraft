import { useState } from 'react'

const SIDEBAR_WIDTH = 280

export default function AgentSidebar({
  agents, selectedAgent, onSelectAgent,
  conversations, selectedConv, onSelectConv, onNewConversation,
  skills, memories,
}) {
  const [tab, setTab] = useState('agents') // agents | skills | memory
  const [search, setSearch] = useState('')

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={{
      width: SIDEBAR_WIDTH, minWidth: SIDEBAR_WIDTH, height: '100%',
      background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-subtle)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 600, color: 'var(--accent-primary)' }}>
            HERMES
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>v0.2</span>
        </div>
        <input
          type="text"
          placeholder="Search..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: '100%', padding: '6px 10px', borderRadius: 6,
            border: '1px solid var(--border-subtle)', background: 'var(--bg-tertiary)',
            color: 'var(--text-primary)', fontSize: 12, outline: 'none',
          }}
        />
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)' }}>
        {['agents', 'skills', 'memory'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            flex: 1, padding: '8px 0', fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
            background: 'none', border: 'none', cursor: 'pointer',
            color: tab === t ? 'var(--accent-primary)' : 'var(--text-tertiary)',
            borderBottom: tab === t ? '2px solid var(--accent-primary)' : '2px solid transparent',
          }}>
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
        {tab === 'agents' && (
          <>
            {filteredAgents.map(agent => (
              <div key={agent.id} onClick={() => onSelectAgent(agent)} style={{
                padding: '8px 16px', cursor: 'pointer',
                background: selectedAgent?.id === agent.id ? 'var(--bg-tertiary)' : 'transparent',
                borderLeft: selectedAgent?.id === agent.id ? '3px solid var(--accent-primary)' : '3px solid transparent',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: 'var(--bg-elevated)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, fontWeight: 600, color: 'var(--accent-primary)',
                  }}>
                    {agent.name.charAt(0)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {agent.name}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                      {agent.llm_model} · {agent.status}
                    </div>
                  </div>
                </div>

                {/* Conversations for selected agent */}
                {selectedAgent?.id === agent.id && (
                  <div style={{ marginTop: 8, marginLeft: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Conversations</span>
                      <button onClick={e => { e.stopPropagation(); onNewConversation() }} style={{
                        fontSize: 10, color: 'var(--accent-primary)', background: 'none', border: 'none', cursor: 'pointer',
                      }}>+ New</button>
                    </div>
                    {conversations.map(conv => (
                      <div key={conv.id} onClick={e => { e.stopPropagation(); onSelectConv(conv) }} style={{
                        padding: '4px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
                        background: selectedConv?.id === conv.id ? 'var(--bg-elevated)' : 'transparent',
                        color: selectedConv?.id === conv.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                        marginBottom: 2,
                      }}>
                        {conv.title || 'Untitled'}
                      </div>
                    ))}
                    {conversations.length === 0 && (
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', padding: '4px 8px' }}>No conversations</div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {filteredAgents.length === 0 && (
              <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
                No agents yet. Create one to get started.
              </div>
            )}
          </>
        )}

        {tab === 'skills' && (
          <div style={{ padding: '0 12px' }}>
            {skills.map(skill => (
              <div key={skill.id} style={{
                padding: '8px 12px', borderRadius: 6, marginBottom: 4,
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{skill.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{skill.description}</div>
                <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                  {skill.tools.map(tool => (
                    <span key={tool} style={{
                      fontSize: 9, padding: '2px 6px', borderRadius: 3,
                      background: 'var(--accent-dim)', color: 'var(--accent-primary)',
                    }}>{tool}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === 'memory' && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
            Select an agent to view its memories.
          </div>
        )}
      </div>
    </div>
  )
}
