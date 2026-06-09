import { useQuery } from '@tanstack/react-query'
import { hermesApi } from '../lib/api'
import { useHermesRunStore } from '../stores/runStore'
import { useHermesRunStream } from '../hooks/useRunStream'

export default function HermesRuns() {
  const { events } = useHermesRunStore()
  const activeRun = useHermesRunStore((s) => s.activeRun)
  const setActiveRun = useHermesRunStore((s) => s.setActiveRun)

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['hermes-runs'],
    queryFn: hermesApi.listRuns,
  })

  useHermesRunStream(activeRun?.id || null)

  const selectRun = (run) => {
    setActiveRun(run)
  }

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '24px' }}>Runs</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Run list */}
        <div>
          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-secondary)' }}>
              Loading runs...
            </div>
          ) : runs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-secondary)' }}>
              No runs yet. Go to Agents to start a run.
            </div>
          ) : (
            <div style={{
              background: 'var(--bg-secondary)',
              borderRadius: '12px',
              border: '1px solid var(--border-subtle)',
              overflow: 'hidden',
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-tertiary)' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Run ID</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Agent</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Status</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Mode</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Duration</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.id}
                      onClick={() => selectRun(run)}
                      style={{
                        borderTop: '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        background: activeRun?.id === run.id ? 'var(--bg-tertiary)' : 'transparent',
                      }}
                    >
                      <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        {run.id.slice(0, 8)}...
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                        {run.agent_id.slice(0, 8)}...
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          fontSize: '12px',
                          fontWeight: '500',
                          borderRadius: '9999px',
                          background: run.status === 'completed' ? '#dcfce7' : run.status === 'running' ? '#fef9c3' : run.status === 'failed' ? '#fecaca' : run.status === 'pending' ? '#dbeafe' : '#f3f4f6',
                          color: run.status === 'completed' ? '#166534' : run.status === 'running' ? '#854d0e' : run.status === 'failed' ? '#991b1b' : run.status === 'pending' ? '#1e40af' : '#374151',
                        }}>
                          {run.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-secondary)' }}>{run.mode}</td>
                      <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-secondary)' }}>
                        {run.duration_ms ? `${run.duration_ms}ms` : '-'}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-secondary)' }}>
                        {run.total_tokens || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Event log sidebar */}
        <div>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: '12px',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ padding: '16px', borderBottom: '1px solid var(--border-subtle)' }}>
              <h2 style={{ fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>Event Log</h2>
              {activeRun && (
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                  Run: {activeRun.id.slice(0, 8)}...
                </p>
              )}
            </div>

            <div style={{ padding: '16px', maxHeight: '400px', overflowY: 'auto' }}>
              {!activeRun ? (
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', textAlign: 'center', padding: '16px 0' }}>
                  Select a run to view events
                </p>
              ) : events.length === 0 ? (
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', textAlign: 'center', padding: '16px 0' }}>
                  Waiting for events...
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {events.map((event, i) => (
                    <div
                      key={event.id || i}
                      style={{
                        fontSize: '12px',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{
                          padding: '2px 6px',
                          fontSize: '10px',
                          fontWeight: '600',
                          borderRadius: '4px',
                          background: event.type?.includes('error') ? '#fecaca' : event.type?.includes('completed') ? '#dcfce7' : event.type?.includes('started') ? '#dbeafe' : '#f3f4f6',
                          color: event.type?.includes('error') ? '#991b1b' : event.type?.includes('completed') ? '#166534' : event.type?.includes('started') ? '#1e40af' : '#374151',
                        }}>
                          {event.type}
                        </span>
                        <span style={{ color: 'var(--text-secondary)' }}>#{event.sequence}</span>
                      </div>
                      <pre style={{
                        color: 'var(--text-secondary)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        margin: 0,
                        fontSize: '11px',
                        fontFamily: 'monospace',
                      }}>
                        {JSON.stringify(event.data, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
