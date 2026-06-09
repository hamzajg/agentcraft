import { useState, useEffect } from 'react'
import { hermesApi } from '../lib/api'

const TOOL_ICONS = {
  shell: '&#128187;',
  git: '&#128230;',
  filesystem: '&#128193;',
  browser: '&#127760;',
}

const TOOL_DESCS = {
  shell: 'Execute shell commands on the host system',
  git: 'Git operations — status, diff, commit, branch, log',
  filesystem: 'Read, write, list, and manage files and directories',
  browser: 'Open URLs and capture page content',
}

export default function ToolsPage() {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedTool, setSelectedTool] = useState(null)
  const [argsInput, setArgsInput] = useState('{}')
  const [executing, setExecuting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadTools()
  }, [])

  const loadTools = async () => {
    try {
      const data = await hermesApi.listTools()
      setTools(data)
    } catch (e) {
      console.error('Failed to load tools:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectTool = (tool) => {
    setSelectedTool(tool)
    setResult(null)
    setError(null)
    // Set default args based on tool
    const defaults = {
      shell: JSON.stringify({ command: 'echo "Hello from Hermes"' }, null, 2),
      git: JSON.stringify({ operation: 'status' }, null, 2),
      filesystem: JSON.stringify({ operation: 'list', path: '.' }, null, 2),
      browser: JSON.stringify({ operation: 'fetch', url: 'https://example.com' }, null, 2),
    }
    setArgsInput(defaults[tool.name] || '{}')
  }

  const handleExecute = async () => {
    setExecuting(true)
    setResult(null)
    setError(null)
    try {
      const args = JSON.parse(argsInput)
      const res = await hermesApi.executeTool(selectedTool.name, args)
      setResult(res)
    } catch (e) {
      if (e instanceof SyntaxError) {
        setError('Invalid JSON in arguments')
      } else {
        setError(e.message)
      }
    } finally {
      setExecuting(false)
    }
  }

  if (loading) return <div style={{ padding: 24, color: 'var(--text-secondary)' }}>Loading tools...</div>

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Tools List */}
      <div style={{ width: 320, borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
            Tools <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 400 }}>({tools.length})</span>
          </h2>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4 }}>
            Execute tools directly or via agent runs
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          {tools.map(tool => (
            <div
              key={tool.name}
              onClick={() => handleSelectTool(tool)}
              style={{
                padding: '12px 14px', borderRadius: 8, cursor: 'pointer', marginBottom: 4,
                background: selectedTool?.name === tool.name ? 'var(--bg-tertiary)' : 'transparent',
                border: `1px solid ${selectedTool?.name === tool.name ? 'var(--border-hover)' : 'transparent'}`,
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 20 }} dangerouslySetInnerHTML={{ __html: TOOL_ICONS[tool.name] || '&#128295;' }} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {tool.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {TOOL_DESCS[tool.name] || 'Execute this tool'}
                  </div>
                </div>
              </div>
              {tool.description && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6, paddingLeft: 30 }}>
                  {tool.description}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Tool Console */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {selectedTool ? (
          <>
            <div style={{
              padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 18 }} dangerouslySetInnerHTML={{ __html: TOOL_ICONS[selectedTool.name] || '&#128295;' }} />
                <div>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {selectedTool.name}
                  </h3>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{TOOL_DESCS[selectedTool.name]}</div>
                </div>
              </div>
              <button onClick={handleExecute} disabled={executing} style={{
                padding: '8px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500, cursor: 'pointer',
                background: executing ? 'var(--bg-elevated)' : 'var(--accent-primary)',
                border: 'none', color: executing ? 'var(--text-tertiary)' : '#000',
              }}>
                {executing ? 'Running...' : 'Execute'}
              </button>
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* Args Editor */}
              <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
                <label style={labelStyle}>Arguments (JSON)</label>
                <textarea
                  value={argsInput}
                  onChange={e => setArgsInput(e.target.value)}
                  rows={8}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 6,
                    border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)',
                    color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-mono)',
                    resize: 'vertical', outline: 'none', boxSizing: 'border-box', lineHeight: 1.5,
                  }}
                  spellCheck={false}
                />
              </div>

              {/* Result Output */}
              <div style={{ flex: 1, overflow: 'auto', padding: '12px 20px' }}>
                <label style={labelStyle}>Output</label>
                {error && (
                  <div style={{
                    padding: '10px 14px', borderRadius: 6, marginBottom: 8,
                    background: '#f04d4d15', border: '1px solid #f04d4d40', color: 'var(--danger)',
                    fontSize: 12, fontFamily: 'var(--font-mono)',
                  }}>
                    {error}
                  </div>
                )}
                {result && (
                  <pre style={{
                    padding: '12px 14px', borderRadius: 6,
                    background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)', fontSize: 12, fontFamily: 'var(--font-mono)',
                    overflow: 'auto', margin: 0, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                  }}>
                    {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                  </pre>
                )}
                {!result && !error && (
                  <div style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>
                    Click Execute to run the tool
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            Select a tool to configure and execute
          </div>
        )}
      </div>
    </div>
  )
}

const labelStyle = {
  display: 'block', fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
  letterSpacing: 0.5, color: 'var(--text-tertiary)', marginBottom: 6,
}
