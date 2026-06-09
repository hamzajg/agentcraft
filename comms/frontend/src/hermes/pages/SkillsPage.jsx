import { useState, useEffect } from 'react'
import { hermesApi } from '../lib/api'

const CATEGORY_COLORS = {
  development: '#10b981',
  content: '#8b5cf6',
  infrastructure: '#f59e0b',
  analysis: '#06b6d4',
  security: '#ef4444',
  optimization: '#f97316',
  design: '#ec4899',
  general: '#6b7280',
}

export default function SkillsPage() {
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedSkill, setSelectedSkill] = useState(null)
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    loadSkills()
  }, [])

  const loadSkills = async () => {
    try {
      const data = await hermesApi.listSkills()
      setSkills(data)
    } catch (e) {
      console.error('Failed to load skills:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = async (skill, e) => {
    e.stopPropagation()
    try {
      const updated = await hermesApi.updateSkill(skill.id, { enabled: !skill.enabled })
      setSkills(prev => prev.map(s => s.id === skill.id ? { ...s, enabled: updated.enabled } : s))
      if (selectedSkill?.id === skill.id) {
        setSelectedSkill(prev => ({ ...prev, enabled: updated.enabled }))
      }
    } catch (e) {
      console.error('Failed to toggle skill:', e)
    }
  }

  const handleSelectSkill = (skill) => {
    setSelectedSkill(skill)
    setEditForm({
      description: skill.description,
      tools: skill.tools.join(', '),
      prompt_sections: Object.entries(skill.prompt_sections || {}).map(([k, v]) => `${k}: ${v}`).join('\n'),
    })
    setEditMode(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const promptSections = {}
      editForm.prompt_sections.split('\n').filter(Boolean).forEach(line => {
        const idx = line.indexOf(':')
        if (idx > 0) {
          promptSections[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
        }
      })
      const data = {
        description: editForm.description,
        tools: editForm.tools.split(',').map(t => t.trim()).filter(Boolean),
        prompt_sections: promptSections,
      }
      const updated = await hermesApi.updateSkill(selectedSkill.id, data)
      setSkills(prev => prev.map(s => s.id === selectedSkill.id ? { ...s, ...updated } : s))
      setSelectedSkill(prev => ({ ...prev, ...updated }))
      setEditMode(false)
    } catch (e) {
      console.error('Failed to save skill:', e)
    } finally {
      setSaving(false)
    }
  }

  const categories = ['all', ...new Set(skills.map(s => s.category))]
  const filtered = filter === 'all' ? skills : skills.filter(s => s.category === filter)

  if (loading) return <div style={{ padding: 24, color: 'var(--text-secondary)' }}>Loading skills...</div>

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Skills List */}
      <div style={{ width: 380, borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
            Skills <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 400 }}>({skills.length})</span>
          </h2>
          <div style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap' }}>
            {categories.map(cat => (
              <button key={cat} onClick={() => setFilter(cat)} style={{
                padding: '3px 10px', borderRadius: 12, fontSize: 11, cursor: 'pointer',
                background: filter === cat ? 'var(--accent-dim)' : 'var(--bg-tertiary)',
                border: `1px solid ${filter === cat ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                color: filter === cat ? 'var(--accent-primary)' : 'var(--text-tertiary)',
                textTransform: 'capitalize',
              }}>
                {cat === 'all' ? 'All' : cat}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          {filtered.map(skill => (
            <div
              key={skill.id}
              onClick={() => handleSelectSkill(skill)}
              style={{
                padding: '10px 12px', borderRadius: 8, cursor: 'pointer', marginBottom: 4,
                background: selectedSkill?.id === skill.id ? 'var(--bg-tertiary)' : 'transparent',
                border: `1px solid ${selectedSkill?.id === skill.id ? 'var(--border-hover)' : 'transparent'}`,
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: CATEGORY_COLORS[skill.category] || '#6b7280',
                  }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{skill.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {skill.description}
                    </div>
                  </div>
                </div>
                {/* Toggle */}
                <button
                  onClick={(e) => handleToggle(skill, e)}
                  style={{
                    width: 36, height: 20, borderRadius: 10, border: 'none', cursor: 'pointer', flexShrink: 0,
                    background: skill.enabled ? 'var(--accent-primary)' : 'var(--bg-elevated)',
                    position: 'relative', transition: 'background 0.2s',
                  }}
                >
                  <div style={{
                    width: 16, height: 16, borderRadius: '50%', background: '#fff',
                    position: 'absolute', top: 2,
                    left: skill.enabled ? 18 : 2, transition: 'left 0.2s',
                  }} />
                </button>
              </div>
              <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                {skill.tools.map(tool => (
                  <span key={tool} style={{
                    fontSize: 9, padding: '2px 6px', borderRadius: 3,
                    background: 'var(--accent-dim)', color: 'var(--accent-primary)',
                  }}>{tool}</span>
                ))}
                <span style={{
                  fontSize: 9, padding: '2px 6px', borderRadius: 3,
                  background: `${CATEGORY_COLORS[skill.category] || '#6b7280'}20`,
                  color: CATEGORY_COLORS[skill.category] || '#6b7280',
                }}>{skill.category}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Skill Detail / Editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {selectedSkill ? (
          <>
            <div style={{
              padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{selectedSkill.name}</h3>
                <span style={{ fontSize: 11, color: CATEGORY_COLORS[selectedSkill.category] || '#6b7280', textTransform: 'capitalize' }}>
                  {selectedSkill.category}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {editMode ? (
                  <>
                    <button onClick={() => setEditMode(false)} style={{
                      padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                      background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                      color: 'var(--text-secondary)',
                    }}>Cancel</button>
                    <button onClick={handleSave} disabled={saving} style={{
                      padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                      background: 'var(--accent-primary)', border: 'none', color: '#000', fontWeight: 500,
                    }}>{saving ? 'Saving...' : 'Save'}</button>
                  </>
                ) : (
                  <button onClick={() => setEditMode(true)} style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                    background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                  }}>Edit</button>
                )}
              </div>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
              {/* Description */}
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Description</label>
                {editMode ? (
                  <input
                    value={editForm.description}
                    onChange={e => setEditForm(p => ({ ...p, description: e.target.value }))}
                    style={inputStyle}
                  />
                ) : (
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selectedSkill.description}</div>
                )}
              </div>

              {/* Tools */}
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Tools</label>
                {editMode ? (
                  <input
                    value={editForm.tools}
                    onChange={e => setEditForm(p => ({ ...p, tools: e.target.value }))}
                    placeholder="shell, filesystem, browser"
                    style={inputStyle}
                  />
                ) : (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {selectedSkill.tools.map(tool => (
                      <span key={tool} style={{
                        fontSize: 12, padding: '4px 10px', borderRadius: 4,
                        background: 'var(--accent-dim)', color: 'var(--accent-primary)',
                        fontFamily: 'var(--font-mono)',
                      }}>{tool}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Prompt Sections */}
              <div>
                <label style={labelStyle}>Prompt Sections</label>
                {editMode ? (
                  <textarea
                    value={editForm.prompt_sections}
                    onChange={e => setEditForm(p => ({ ...p, prompt_sections: e.target.value }))}
                    rows={6}
                    placeholder={"key: prompt text\nkey2: another prompt"}
                    style={{ ...inputStyle, fontFamily: 'var(--font-mono)', resize: 'vertical' }}
                  />
                ) : (
                  <div style={{ background: 'var(--bg-tertiary)', borderRadius: 6, padding: 12, border: '1px solid var(--border-subtle)' }}>
                    {Object.entries(selectedSkill.prompt_sections || {}).map(([key, text]) => (
                      <div key={key} style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)', marginBottom: 2 }}>
                          {key}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{text}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            Select a skill to view and edit its configuration
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

const inputStyle = {
  width: '100%', padding: '8px 12px', borderRadius: 6,
  border: '1px solid var(--border-subtle)', background: 'var(--bg-tertiary)',
  color: 'var(--text-primary)', fontSize: 13, outline: 'none',
  fontFamily: 'var(--font-body)', boxSizing: 'border-box',
}
