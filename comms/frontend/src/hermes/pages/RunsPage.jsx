import { useState, useEffect, useRef, useCallback } from 'react'
import { hermesApi } from '../lib/api'

const STATUS_STYLES = {
  pending: { bg: '#f59e0b20', color: '#f59e0b', label: 'Pending' },
  running: { bg: '#00d4ff20', color: '#00d4ff', label: 'Running' },
  completed: { bg: '#10b98120', color: '#10b981', label: 'Completed' },
  failed: { bg: '#f04d4d20', color: '#f04d4d', label: 'Failed' },
  cancelled: { bg: '#6b728020', color: '#6b7280', label: 'Cancelled' },
}

const EVENT_ICONS = {
  run_started: '&#9654;',
  run_completed: '&#9989;',
  run_failed: '&#10060;',
  tool_called: '&#128295;',
  tool_result: '&#128230;',
  thinking: '&#129504;',
  token: '&#9998;',
  message_sent: '&#128172;',
  message_received: '&#128172;',
  error: '&#9888;',
}

export default function RunsPage() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState(null)
  const [events, setEvents] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [filter, setFilter] = useState('all')
  const eventSourceRef = useRef(null)
  const eventsEndRef = useRef(null)

  useEffect(() => {
    loadRuns()
  }, [])

  const loadRuns = async () => {
    try {
      const data = await hermesApi.listRuns()
      setRuns(data)
    } catch (e) {
      console.error('Failed to load runs:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectRun = useCallback(async (run) => {
    setSelectedRun(run)
    setEvents([])
    try {
      const evts = await hermesApi.getRunEvents(run.id)
      setEvents(evts)
    } catch (e) {
      console.error('Failed to load events:', e)
    }
  }, [])

  const handleStreamRun = useCallback((run) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    setStreaming(true)
    setEvents([])

    const es = hermesApi.streamRun(run.id)
    eventSourceRef.current = es

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        setEvents(prev => [...prev, event])
        // Auto-update run status from events
        if (event.event_type === 'run_completed') {
          setRuns(prev => prev.map(r => r.id === run.id ? { ...r, status: 'completed' } : r))
          setStreaming(false)
          es.close()
        } else if (event.event_type === 'run_failed') {
          setRuns(prev => prev.map(r => r.id === run.id ? { ...r, status: 'failed' } : r))
          setStreaming(false)
          es.close()
        }
      } catch (err) {
        console.error('Failed to parse event:', err)
      }
    }

    es.onerror = () => {
      setStreaming(false)
      es.close()
    }
  }, [])

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  const filtered = filter === 'all' ? runs : runs.filter(r => r.status === filter)

  const formatTime = (ts) => {
    if (!ts) return '-'
    const d = new Date(ts)
    return d.toLocaleTimeString()
  }

  if (loading) return <div style={{ padding: 24, color: 'var(--text-secondary)' }}>Loading runs...</div>

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Runs List */}
      <div style={{ width: 360, borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
            Runs <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 400 }}>({runs.length})</span>
          </h2>
          <div style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap' }}>
            {['all', 'pending', 'running', 'completed', 'failed'].map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: '3px 10px', borderRadius: 12, fontSize: 11, cursor: 'pointer',
                background: filter === f ? 'var(--accent-dim)' : 'var(--bg-tertiary)',
                border: `1px solid ${filter === f ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                color: filter === f ? 'var(--accent-primary)' : 'var(--text-tertiary)',
                textTransform: 'capitalize',
              }}>
                {f}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
              No runs found
            </div>
          ) : (
            filtered.map(run => {
              const statusStyle = STATUS_STYLES[run.status] || STATUS_STYLES.pending
              return (
                <div
                  key={run.id}
                  onClick={() => handleSelectRun(run)}
                  style={{
                    padding: '10px 12px', borderRadius: 8, cursor: 'pointer', marginBottom: 4,
                    background: selectedRun?.id === run.id ? 'var(--bg-tertiary)' : 'transparent',
                    border: `1px solid ${selectedRun?.id === run.id ? 'var(--border-hover)' : 'transparent'}`,
                    transition: 'all 0.15s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {run.id.slice(0, 8)}...
                    </span>
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 10,
                      background: statusStyle.bg, color: statusStyle.color, fontWeight: 500,
                    }}>
                      {statusStyle.label}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--text-tertiary)' }}>
                    <span>Mode: {run.mode}</span>
                    <span>Created: {formatTime(run.created_at)}</span>
                  </div>
                  {run.input_data && (
                    <div style={{
                      marginTop: 6, fontSize: 11, color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {typeof run.input_data === 'string' ? run.input_data : JSON.stringify(run.input_data)}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Run Detail / Events */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {selectedRun ? (
          <>
            <div style={{
              padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                  Run <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-tertiary)' }}>{selectedRun.id.slice(0, 12)}...</span>
                </h3>
                <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 11, color: 'var(--text-tertiary)' }}>
                  <span>Status: <span style={{ color: STATUS_STYLES[selectedRun.status]?.color }}>{STATUS_STYLES[selectedRun.status]?.label}</span></span>
                  <span>Mode: {selectedRun.mode}</span>
                  <span>Agent: {selectedRun.agent_id?.slice(0, 8) || '-'}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => handleStreamRun(selectedRun)} disabled={streaming} style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  background: streaming ? 'var(--bg-elevated)' : 'var(--accent-dim)',
                  border: `1px solid ${streaming ? 'var(--border-subtle)' : 'var(--accent-primary)'}`,
                  color: streaming ? 'var(--text-tertiary)' : 'var(--accent-primary)',
                }}>
                  {streaming ? 'Streaming...' : 'Stream Events'}
                </button>
                <button onClick={loadRuns} style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                }}>Refresh</button>
              </div>
            </div>

            {/* Events Stream */}
            <div style={{ flex: 1, overflow: 'auto', padding: '12px 20px' }}>
              <label style={labelStyle}>Event Stream ({events.length} events)</label>
              {events.length === 0 ? (
                <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
                  No events. Click "Stream Events" to start listening.
                </div>
              ) : (
                events.map((evt, i) => (
                  <div key={evt.id || i} style={{
                    display: 'flex', gap: 10, padding: '8px 12px', borderRadius: 6, marginBottom: 4,
                    background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                  }}>
                    <span style={{ fontSize: 14 }} dangerouslySetInnerHTML={{ __html: EVENT_ICONS[evt.event_type] || '&#128196;' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{
                          fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)',
                          color: evt.event_type?.includes('failed') ? 'var(--danger)' :
                            evt.event_type?.includes('completed') ? 'var(--success)' :
                              evt.event_type?.includes('tool') ? 'var(--warning)' : 'var(--accent-primary)',
                        }}>
                          {evt.event_type}
                        </span>
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                          {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
                        </span>
                      </div>
                      {evt.data && (
                        <pre style={{
                          margin: '4px 0 0', padding: '6px 8px', borderRadius: 4,
                          background: 'var(--bg-primary)', fontSize: 11, fontFamily: 'var(--font-mono)',
                          color: 'var(--text-secondary)', overflow: 'auto', maxHeight: 150,
                          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                        }}>
                          {typeof evt.data === 'string' ? evt.data : JSON.stringify(evt.data, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={eventsEndRef} />
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            Select a run to view events and stream real-time updates
          </div>
        )}
      </div>
    </div>
  )
}

const labelStyle = {
  display: 'block', fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
  letterSpacing: 0.5, color: 'var(--text-tertiary)', marginBottom: 8,
}
