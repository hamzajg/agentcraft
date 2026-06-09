import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { hermesApi } from '../lib/api'

export default function HermesAgents() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editingAgent, setEditingAgent] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    system_prompt: '',
    user_template: '',
    llm_provider: 'ollama',
    llm_model: 'llama3.2',
    temperature: 0.7,
    framework: 'raw',
  })
  const [selectedAgentForRun, setSelectedAgentForRun] = useState(null)
  const [runInputKey, setRunInputKey] = useState('topic')
  const [runInputValue, setRunInputValue] = useState('')

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ['hermes-agents'],
    queryFn: hermesApi.listAgents,
  })

  const createMutation = useMutation({
    mutationFn: hermesApi.createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hermes-agents'] })
      setShowCreate(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => hermesApi.updateAgent(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hermes-agents'] })
      setEditingAgent(null)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: hermesApi.deleteAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hermes-agents'] })
    },
  })

  const runMutation = useMutation({
    mutationFn: hermesApi.createRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hermes-runs'] })
      setSelectedAgentForRun(null)
      setRunInputValue('')
    },
  })

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      system_prompt: '',
      user_template: '',
      llm_provider: 'ollama',
      llm_model: 'llama3.2',
      temperature: 0.7,
      framework: 'raw',
    })
  }

  const handleSubmit = () => {
    if (editingAgent) {
      updateMutation.mutate({ id: editingAgent.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleRun = (agentId) => {
    const inputData = runInputKey && runInputValue ? { [runInputKey]: runInputValue } : {}
    runMutation.mutate({
      agent_id: agentId,
      mode: 'sync',
      input_data: inputData,
    })
  }

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    background: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
  }

  const labelStyle = {
    display: 'block',
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-secondary)',
    marginBottom: '4px',
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)' }}>Agents</h1>
        <button
          onClick={() => {
            setShowCreate(true)
            setEditingAgent(null)
            resetForm()
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            background: 'var(--accent-primary)',
            color: 'var(--bg-primary)',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '500',
          }}
        >
          + New Agent
        </button>
      </div>

      {/* Agent form modal */}
      {(showCreate || editingAgent) && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 50,
        }}>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: '12px',
            padding: '24px',
            width: '100%',
            maxWidth: '600px',
            maxHeight: '90vh',
            overflowY: 'auto',
          }}>
            <h2 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
              {editingAgent ? 'Edit Agent' : 'Create Agent'}
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={labelStyle}>Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  style={inputStyle}
                  placeholder="My Agent"
                />
              </div>

              <div>
                <label style={labelStyle}>Description</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  style={inputStyle}
                  placeholder="A helpful assistant"
                />
              </div>

              <div>
                <label style={labelStyle}>System Prompt</label>
                <textarea
                  value={formData.system_prompt}
                  onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                  rows={4}
                  style={{ ...inputStyle, resize: 'vertical' }}
                  placeholder="You are a helpful assistant..."
                />
              </div>

              <div>
                <label style={labelStyle}>User Template</label>
                <textarea
                  value={formData.user_template}
                  onChange={(e) => setFormData({ ...formData, user_template: e.target.value })}
                  rows={2}
                  style={{ ...inputStyle, resize: 'vertical' }}
                  placeholder="Research the following topic: {{topic}}"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={labelStyle}>LLM Provider</label>
                  <select
                    value={formData.llm_provider}
                    onChange={(e) => setFormData({ ...formData, llm_provider: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="ollama">Ollama</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="gemini">Gemini</option>
                    <option value="groq">Groq</option>
                  </select>
                </div>

                <div>
                  <label style={labelStyle}>Model</label>
                  <input
                    type="text"
                    value={formData.llm_model}
                    onChange={(e) => setFormData({ ...formData, llm_model: e.target.value })}
                    style={inputStyle}
                    placeholder="llama3.2"
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={labelStyle}>Temperature</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={formData.temperature}
                    onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                    style={inputStyle}
                  />
                </div>

                <div>
                  <label style={labelStyle}>Framework</label>
                  <select
                    value={formData.framework}
                    onChange={(e) => setFormData({ ...formData, framework: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="raw">Raw API</option>
                    <option value="langchain">LangChain</option>
                    <option value="crewai">CrewAI</option>
                    <option value="autogen">AutoGen</option>
                    <option value="llamaindex">LlamaIndex</option>
                  </select>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
              <button
                onClick={handleSubmit}
                disabled={createMutation.isPending || updateMutation.isPending}
                style={{
                  padding: '8px 16px',
                  background: 'var(--accent-primary)',
                  color: 'var(--bg-primary)',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: '500',
                  opacity: createMutation.isPending || updateMutation.isPending ? 0.5 : 1,
                }}
              >
                {editingAgent ? 'Update' : 'Create'}
              </button>
              <button
                onClick={() => {
                  setShowCreate(false)
                  setEditingAgent(null)
                }}
                style={{
                  padding: '8px 16px',
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Run modal */}
      {selectedAgentForRun && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 50,
        }}>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: '12px',
            padding: '24px',
            width: '100%',
            maxWidth: '400px',
          }}>
            <h2 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
              Run Agent
            </h2>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Provide input data as key-value pairs for template variables.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px' }}>
              <div>
                <label style={labelStyle}>Input Key</label>
                <input
                  type="text"
                  value={runInputKey}
                  onChange={(e) => setRunInputKey(e.target.value)}
                  style={inputStyle}
                  placeholder="topic"
                />
              </div>
              <div>
                <label style={labelStyle}>Input Value</label>
                <input
                  type="text"
                  value={runInputValue}
                  onChange={(e) => setRunInputValue(e.target.value)}
                  style={inputStyle}
                  placeholder="The future of AI"
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => handleRun(selectedAgentForRun)}
                style={{
                  padding: '8px 16px',
                  background: '#16a34a',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: '500',
                }}
              >
                ▶ Run
              </button>
              <button
                onClick={() => setSelectedAgentForRun(null)}
                style={{
                  padding: '8px 16px',
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Agent list */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-secondary)' }}>
          Loading agents...
        </div>
      ) : agents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px' }}>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>No agents created yet</p>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              padding: '8px 16px',
              background: 'var(--accent-primary)',
              color: 'var(--bg-primary)',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            Create your first agent
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {agents.map((agent) => (
            <div
              key={agent.id}
              style={{
                background: 'var(--bg-secondary)',
                borderRadius: '12px',
                padding: '16px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>{agent.name}</h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>{agent.id}</p>
                </div>
                <span style={{
                  padding: '2px 8px',
                  fontSize: '12px',
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-secondary)',
                  borderRadius: '4px',
                }}>
                  {agent.framework}
                </span>
              </div>

              <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px', lineHeight: '1.4' }}>
                {agent.description || 'No description'}
              </p>

              <div style={{ display: 'flex', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                <span style={{ padding: '2px 8px', background: 'var(--bg-tertiary)', borderRadius: '4px' }}>{agent.llm_provider}</span>
                <span style={{ padding: '2px 8px', background: 'var(--bg-tertiary)', borderRadius: '4px' }}>{agent.llm_model}</span>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setSelectedAgentForRun(agent.id)}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '4px',
                    padding: '8px',
                    background: '#16a34a',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '500',
                  }}
                >
                  ▶ Run
                </button>
                <button
                  onClick={() => {
                    setEditingAgent(agent)
                    setFormData(agent)
                  }}
                  style={{
                    padding: '8px 12px',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                  }}
                >
                  ✏️
                </button>
                <button
                  onClick={() => deleteMutation.mutate(agent.id)}
                  style={{
                    padding: '8px 12px',
                    background: '#fecaca',
                    color: '#991b1b',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                  }}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
