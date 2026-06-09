import { useState, useEffect } from 'react'
import { hermesApi } from '../lib/api'

const PROVIDER_COLORS = {
  openai: '#10b981', anthropic: '#f59e0b', ollama: '#06b6d4',
  gemini: '#8b5cf6', groq: '#ef4444', lm_studio: '#ec4899',
  azure_openai: '#3b82f6', cohere: '#f97316', huggingface: '#ff7a4d',
  together: '#10b981',
}

const EMPTY_FORM = {
  name: '', description: '', system_prompt: 'You are a helpful assistant.',
  goal: '', persona: '', llm_provider: 'ollama', llm_model: 'llama3.2',
  temperature: 0.7, max_tokens: '', framework: 'raw', skills: [],
  tools_enabled: [],
}

export default function AgentsFactoryPage({ onAgentCreated }) {
  const [dbAgents, setDbAgents] = useState([])
  const [factoryAgents, setFactoryAgents] = useState({ legacy: [], hermes_yaml: [] })
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('db') // db | yaml | create
  const [importing, setImporting] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [creating, setCreating] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [allSkills, setAllSkills] = useState([])
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    try {
      const [db, factory, skills] = await Promise.all([
        hermesApi.listAgents(),
        hermesApi.listFactoryAgents(),
        hermesApi.listSkills(),
      ])
      setDbAgents(db)
      setFactoryAgents(factory)
      setAllSkills(skills)
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }

  const handleImport = async (source, agentId) => {
    setImporting(agentId)
    try {
      await hermesApi.importAgent(source, agentId)
      await loadAll()
      setTab('db')
    } catch (e) { console.error('Import failed:', e) } finally { setImporting(null) }
  }

  const handleCreate = async () => {
    setCreating(true)
    try {
      const data = { ...form }
      if (data.max_tokens === '') data.max_tokens = null
      else data.max_tokens = parseInt(data.max_tokens)
      const agent = await hermesApi.createFromFactory(data)
      setDbAgents(prev => [...prev, agent])
      setForm(EMPTY_FORM)
      setTab('db')
      if (onAgentCreated) onAgentCreated(agent)
    } catch (e) { console.error('Create failed:', e) } finally { setCreating(false) }
  }

  const handleDelete = async (agentId) => {
    try {
      await hermesApi.deleteAgent(agentId)
      setDbAgents(prev => prev.filter(a => a.id !== agentId))
      setSelectedAgent(null)
      setDeleteConfirm(null)
    } catch (e) { console.error('Delete failed:', e) }
  }

  const handleToggleSkill = (skillId) => {
    setForm(prev => ({
      ...prev,
      skills: prev.skills.includes(skillId)
        ? prev.skills.filter(s => s !== skillId)
        : [...prev.skills, skillId],
    }))
  }

  if (loading) return <div style={{ padding: 24, color: 'var(--text-secondary)' }}>Loading agents...</div>

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left: Agent List */}
      <div style={{ width: 400, borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column' }}>
        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)' }}>
          {[
            { id: 'db', label: `My Agents (${dbAgents.length})` },
            { id: 'yaml', label: `Factory (${factoryAgents.legacy.length + factoryAgents.hermes_yaml.length})` },
            { id: 'create', label: '+ New' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              flex: 1, padding: '10px 0', fontSize: 12, fontWeight: 500, cursor: 'pointer',
              background: 'none', border: 'none',
              color: tab === t.id ? 'var(--accent-primary)' : 'var(--text-tertiary)',
              borderBottom: tab === t.id ? '2px solid var(--accent-primary)' : '2px solid transparent',
            }}>{t.label}</button>
          ))}
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          {/* DB Agents */}
          {tab === 'db' && dbAgents.map(agent => (
            <div key={agent.id} onClick={() => setSelectedAgent(agent)} style={{
              padding: '10px 12px', borderRadius: 8, cursor: 'pointer', marginBottom: 4,
              background: selectedAgent?.id === agent.id ? 'var(--bg-tertiary)' : 'transparent',
              border: `1px solid ${selectedAgent?.id === agent.id ? 'var(--border-hover)' : 'transparent'}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: `${PROVIDER_COLORS[agent.llm_provider] || '#6b7280'}20`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 16, fontWeight: 700, color: PROVIDER_COLORS[agent.llm_provider] || '#6b7280',
                }}>{agent.name.charAt(0)}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{agent.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {agent.llm_provider}/{agent.llm_model} · {agent.framework}
                  </div>
                </div>
                <span style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 3,
                  background: agent.status === 'running' ? '#10b98120' : 'var(--bg-elevated)',
                  color: agent.status === 'running' ? 'var(--success)' : 'var(--text-tertiary)',
                }}>{agent.status}</span>
              </div>
              {agent.skills?.length > 0 && (
                <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap', paddingLeft: 46 }}>
                  {agent.skills.slice(0, 3).map(s => (
                    <span key={s} style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: 'var(--accent-dim)', color: 'var(--accent-primary)' }}>{s}</span>
                  ))}
                  {agent.skills.length > 3 && <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>+{agent.skills.length - 3}</span>}
                </div>
              )}
            </div>
          ))}

          {/* YAML Factory Agents */}
          {tab === 'yaml' && (
            <>
              {factoryAgents.legacy.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)', padding: '4px 12px', letterSpacing: 0.5 }}>
                    Legacy Agents ({factoryAgents.legacy.length})
                  </div>
                  {factoryAgents.legacy.map(agent => (
                    <div key={agent.id} style={{
                      padding: '10px 12px', borderRadius: 8, marginBottom: 4,
                      background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{agent.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Legacy · {agent.source_path}</div>
                        </div>
                        <button
                          onClick={() => handleImport('legacy', agent.id)}
                          disabled={importing === agent.id || dbAgents.some(a => a.config?.original_id === agent.id)}
                          style={{
                            padding: '5px 12px', borderRadius: 5, fontSize: 11, cursor: 'pointer',
                            background: dbAgents.some(a => a.config?.original_id === agent.id) ? 'var(--bg-elevated)' : 'var(--accent-dim)',
                            border: `1px solid ${dbAgents.some(a => a.config?.original_id === agent.id) ? 'var(--border-subtle)' : 'var(--accent-primary)'}`,
                            color: dbAgents.some(a => a.config?.original_id === agent.id) ? 'var(--text-tertiary)' : 'var(--accent-primary)',
                          }}
                        >
                          {dbAgents.some(a => a.config?.original_id === agent.id) ? 'Imported' : importing === agent.id ? '...' : 'Import'}
                        </button>
                      </div>
                      {agent.skills?.length > 0 && (
                        <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                          {agent.skills.map(s => (
                            <span key={s} style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: 'var(--accent-dim)', color: 'var(--accent-primary)' }}>{s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {factoryAgents.hermes_yaml.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)', padding: '4px 12px', letterSpacing: 0.5 }}>
                    Hermes YAML Agents ({factoryAgents.hermes_yaml.length})
                  </div>
                  {factoryAgents.hermes_yaml.map(agent => (
                    <div key={agent.id} style={{
                      padding: '10px 12px', borderRadius: 8, marginBottom: 4,
                      background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{agent.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                            {agent.llm_provider}/{agent.llm_model} · v{agent.version}
                          </div>
                        </div>
                        <button
                          onClick={() => handleImport('hermes_yaml', agent.id)}
                          disabled={importing === agent.id || dbAgents.some(a => a.config?.original_id === agent.id)}
                          style={{
                            padding: '5px 12px', borderRadius: 5, fontSize: 11, cursor: 'pointer',
                            background: dbAgents.some(a => a.config?.original_id === agent.id) ? 'var(--bg-elevated)' : 'var(--accent-dim)',
                            border: `1px solid ${dbAgents.some(a => a.config?.original_id === agent.id) ? 'var(--border-subtle)' : 'var(--accent-primary)'}`,
                            color: dbAgents.some(a => a.config?.original_id === agent.id) ? 'var(--text-tertiary)' : 'var(--accent-primary)',
                          }}
                        >
                          {dbAgents.some(a => a.config?.original_id === agent.id) ? 'Imported' : importing === agent.id ? '...' : 'Import'}
                        </button>
                      </div>
                      {agent.description && (
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>{agent.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Create New */}
          {tab === 'create' && (
            <div style={{ padding: '0 4px' }}>
              <FormField label="Name">
                <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="My Agent" style={inputStyle} />
              </FormField>
              <FormField label="Description">
                <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="What does this agent do?" style={inputStyle} />
              </FormField>
              <FormField label="System Prompt">
                <textarea value={form.system_prompt} onChange={e => setForm(p => ({ ...p, system_prompt: e.target.value }))} rows={4} style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-mono)' }} />
              </FormField>
              <FormField label="Goal (optional)">
                <input value={form.goal} onChange={e => setForm(p => ({ ...p, goal: e.target.value }))} placeholder="Primary goal" style={inputStyle} />
              </FormField>
              <FormField label="Persona (optional)">
                <input value={form.persona} onChange={e => setForm(p => ({ ...p, persona: e.target.value }))} placeholder="e.g. expert coder, careful reviewer" style={inputStyle} />
              </FormField>
              <div style={{ display: 'flex', gap: 8 }}>
                <FormField label="Provider" style={{ flex: 1 }}>
                  <select value={form.llm_provider} onChange={e => setForm(p => ({ ...p, llm_provider: e.target.value }))} style={inputStyle}>
                    {['ollama', 'openai', 'anthropic', 'gemini', 'groq', 'lm_studio', 'azure_openai', 'cohere', 'huggingface', 'together'].map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </FormField>
                <FormField label="Model" style={{ flex: 1 }}>
                  <input value={form.llm_model} onChange={e => setForm(p => ({ ...p, llm_model: e.target.value }))} style={inputStyle} />
                </FormField>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <FormField label="Temperature" style={{ flex: 1 }}>
                  <input type="number" min="0" max="2" step="0.1" value={form.temperature} onChange={e => setForm(p => ({ ...p, temperature: parseFloat(e.target.value) }))} style={inputStyle} />
                </FormField>
                <FormField label="Max Tokens" style={{ flex: 1 }}>
                  <input type="number" value={form.max_tokens} onChange={e => setForm(p => ({ ...p, max_tokens: e.target.value }))} placeholder="optional" style={inputStyle} />
                </FormField>
              </div>
              <FormField label="Framework">
                <select value={form.framework} onChange={e => setForm(p => ({ ...p, framework: e.target.value }))} style={inputStyle}>
                  {['raw', 'langchain', 'crewai', 'autogen', 'llamaindex'].map(f => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </FormField>
              <FormField label="Skills">
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {allSkills.map(s => (
                    <button key={s.id} onClick={() => handleToggleSkill(s.id)} style={{
                      padding: '3px 8px', borderRadius: 4, fontSize: 10, cursor: 'pointer',
                      background: form.skills.includes(s.id) ? 'var(--accent-primary)' : 'var(--bg-elevated)',
                      border: `1px solid ${form.skills.includes(s.id) ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                      color: form.skills.includes(s.id) ? '#000' : 'var(--text-tertiary)',
                    }}>{s.name}</button>
                  ))}
                </div>
              </FormField>
              <button onClick={handleCreate} disabled={creating || !form.name.trim()} style={{
                width: '100%', padding: '10px', borderRadius: 8, marginTop: 12, fontSize: 13, fontWeight: 500, cursor: 'pointer',
                background: form.name.trim() && !creating ? 'var(--accent-primary)' : 'var(--bg-elevated)',
                border: 'none', color: form.name.trim() && !creating ? '#000' : 'var(--text-tertiary)',
              }}>{creating ? 'Creating...' : 'Create Agent'}</button>
            </div>
          )}
        </div>
      </div>

      {/* Right: Agent Detail */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {selectedAgent ? (
          <>
            <div style={{
              padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 10,
                  background: `${PROVIDER_COLORS[selectedAgent.llm_provider] || '#6b7280'}20`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 20, fontWeight: 700, color: PROVIDER_COLORS[selectedAgent.llm_provider] || '#6b7280',
                }}>{selectedAgent.name.charAt(0)}</div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>{selectedAgent.name}</h3>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {selectedAgent.llm_provider}/{selectedAgent.llm_model} · {selectedAgent.framework} · {selectedAgent.status}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => setDeleteConfirm(selectedAgent)} style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  background: '#f04d4d15', border: '1px solid #f04d4d40', color: 'var(--danger)',
                }}>Delete</button>
              </div>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
              {selectedAgent.description && (
                <Section title="Description">
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selectedAgent.description}</div>
                </Section>
              )}
              {selectedAgent.system_prompt && (
                <Section title="System Prompt">
                  <pre style={preStyle}>{selectedAgent.system_prompt}</pre>
                </Section>
              )}
              {selectedAgent.goal && (
                <Section title="Goal">
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selectedAgent.goal}</div>
                </Section>
              )}
              {selectedAgent.persona && (
                <Section title="Persona">
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selectedAgent.persona}</div>
                </Section>
              )}
              {selectedAgent.skills?.length > 0 && (
                <Section title="Skills">
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {selectedAgent.skills.map(s => (
                      <span key={s} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 4, background: 'var(--accent-dim)', color: 'var(--accent-primary)' }}>{s}</span>
                    ))}
                  </div>
                </Section>
              )}
              <Section title="Configuration">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <KV k="Provider" v={selectedAgent.llm_provider} />
                  <KV k="Model" v={selectedAgent.llm_model} />
                  <KV k="Temperature" v={selectedAgent.temperature} />
                  <KV k="Framework" v={selectedAgent.framework} />
                  <KV k="Max Tokens" v={selectedAgent.max_tokens || 'default'} />
                  <KV k="Status" v={selectedAgent.status} />
                </div>
              </Section>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>&#129302;</div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Agent Factory</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>Select an agent or create a new one</div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }} onClick={() => setDeleteConfirm(null)}>
          <div style={{
            padding: 20, borderRadius: 12, background: 'var(--bg-secondary)',
            border: '1px solid var(--border-subtle)', maxWidth: 400, width: '100%',
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: 0, fontSize: 15, color: 'var(--text-primary)' }}>Delete Agent?</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8 }}>
              This will permanently delete <strong>{deleteConfirm.name}</strong> and all its conversations, artifacts, and memories.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <button onClick={() => setDeleteConfirm(null)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>Cancel</button>
              <button onClick={() => handleDelete(deleteConfirm.id)} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', background: 'var(--danger)', border: 'none', color: '#fff' }}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-tertiary)', marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  )
}

function FormField({ label, children, style }) {
  return (
    <div style={{ marginBottom: 10, ...style }}>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-tertiary)', marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  )
}

function KV({ k, v }) {
  return (
    <div style={{ padding: '6px 10px', borderRadius: 4, background: 'var(--bg-tertiary)' }}>
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>{k}</div>
      <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 2 }}>{String(v)}</div>
    </div>
  )
}

const inputStyle = {
  width: '100%', padding: '7px 10px', borderRadius: 6,
  border: '1px solid var(--border-subtle)', background: 'var(--bg-tertiary)',
  color: 'var(--text-primary)', fontSize: 12, outline: 'none',
  fontFamily: 'var(--font-body)', boxSizing: 'border-box',
}

const preStyle = {
  padding: '10px 12px', borderRadius: 6, background: 'var(--bg-tertiary)',
  border: '1px solid var(--border-subtle)', fontSize: 12, fontFamily: 'var(--font-mono)',
  color: 'var(--text-secondary)', overflow: 'auto', maxHeight: 200,
  whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, lineHeight: 1.5,
}
