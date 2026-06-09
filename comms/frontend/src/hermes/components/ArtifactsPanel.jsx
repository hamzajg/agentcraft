import { useState } from 'react'

const PANEL_WIDTH = 340

const TYPE_ICONS = {
  document: '&#128196;',
  code: '&#128187;',
  image: '&#127912;',
  data: '&#128202;',
  config: '&#9881;',
}

export default function ArtifactsPanel({ agent, artifacts, onClose }) {
  const [selectedArtifact, setSelectedArtifact] = useState(null)
  const [filter, setFilter] = useState('all')

  const filtered = filter === 'all' ? artifacts : artifacts.filter(a => a.artifact_type === filter)

  return (
    <div style={{
      width: PANEL_WIDTH, minWidth: PANEL_WIDTH, height: '100%',
      background: 'var(--bg-secondary)', borderLeft: '1px solid var(--border-subtle)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px', borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Artifacts</span>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: 'var(--text-tertiary)',
          cursor: 'pointer', fontSize: 16, padding: 0,
        }}>&#10005;</button>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', padding: '0 12px' }}>
        {['all', 'document', 'code', 'image', 'data'].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: '6px 10px', fontSize: 11, textTransform: 'capitalize',
            background: 'none', border: 'none', cursor: 'pointer',
            color: filter === f ? 'var(--accent-primary)' : 'var(--text-tertiary)',
            borderBottom: filter === f ? '2px solid var(--accent-primary)' : '2px solid transparent',
          }}>
            {f}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
        {selectedArtifact ? (
          <div style={{ padding: '0 12px' }}>
            <button onClick={() => setSelectedArtifact(null)} style={{
              fontSize: 11, color: 'var(--accent-primary)', background: 'none',
              border: 'none', cursor: 'pointer', marginBottom: 8,
            }}>&#8592; Back to list</button>
            <div style={{
              padding: 12, borderRadius: 8, background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-subtle)',
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
                {selectedArtifact.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>
                {selectedArtifact.artifact_type} · v{selectedArtifact.version}
              </div>
              <pre style={{
                fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                background: 'var(--bg-primary)', padding: 12, borderRadius: 6,
                overflow: 'auto', maxHeight: 300, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                margin: 0,
              }}>
                {selectedArtifact.content || '(empty)'}
              </pre>
              {selectedArtifact.tags?.length > 0 && (
                <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                  {selectedArtifact.tags.map(tag => (
                    <span key={tag} style={{
                      fontSize: 9, padding: '2px 6px', borderRadius: 3,
                      background: 'var(--accent-dim)', color: 'var(--accent-primary)',
                    }}>{tag}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
            {filtered.length === 0 ? (
              <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
                {artifacts.length === 0 ? 'No artifacts yet' : 'No artifacts match filter'}
              </div>
            ) : (
              filtered.map(artifact => (
                <div key={artifact.id} onClick={() => setSelectedArtifact(artifact)} style={{
                  padding: '8px 12px', margin: '0 8px', borderRadius: 6, cursor: 'pointer',
                  background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                  marginBottom: 4,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 16 }} dangerouslySetInnerHTML={{ __html: TYPE_ICONS[artifact.artifact_type] || '&#128196;' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {artifact.name}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                        {artifact.artifact_type} · v{artifact.version}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </>
        )}
      </div>
    </div>
  )
}
