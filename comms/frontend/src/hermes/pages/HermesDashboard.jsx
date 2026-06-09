import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { hermesApi } from '../lib/api'

export default function HermesDashboard() {
  const { data: agents = [] } = useQuery({
    queryKey: ['hermes-agents'],
    queryFn: hermesApi.listAgents,
  })

  const { data: runs = [] } = useQuery({
    queryKey: ['hermes-runs'],
    queryFn: hermesApi.listRuns,
  })

  const stats = [
    { label: 'Agents', value: agents.length, color: 'bg-hermes-500' },
    { label: 'Total Runs', value: runs.length, color: 'bg-green-500' },
    {
      label: 'Running',
      value: runs.filter((r) => r.status === 'running').length,
      color: 'bg-yellow-500',
    },
    {
      label: 'Completed',
      value: runs.filter((r) => r.status === 'completed').length,
      color: 'bg-purple-500',
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '24px' }}>
        Hermes Dashboard
      </h1>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        {stats.map((stat) => (
          <div
            key={stat.label}
            style={{
              background: 'var(--bg-secondary)',
              borderRadius: '12px',
              padding: '16px',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '4px' }}>{stat.label}</p>
            <p style={{ fontSize: '28px', fontWeight: 'bold', color: 'var(--text-primary)' }}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        <Link
          to="/hermes/agents"
          style={{
            background: 'var(--bg-secondary)',
            borderRadius: '12px',
            padding: '24px',
            border: '1px solid var(--border-subtle)',
            textDecoration: 'none',
            transition: 'border-color 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-primary)'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
        >
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🤖</div>
          <h3 style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>Manage Agents</h3>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
            Create, edit, and configure your AI agents
          </p>
        </Link>

        <Link
          to="/hermes/runs"
          style={{
            background: 'var(--bg-secondary)',
            borderRadius: '12px',
            padding: '24px',
            border: '1px solid var(--border-subtle)',
            textDecoration: 'none',
            transition: 'border-color 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-primary)'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
        >
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>▶️</div>
          <h3 style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>View Runs</h3>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
            Monitor agent executions and view results
          </p>
        </Link>
      </div>

      {/* Recent runs */}
      {runs.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
            Recent Runs
          </h2>
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
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Status</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Mode</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Duration</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 5).map((run) => (
                  <tr key={run.id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                      {run.id.slice(0, 8)}...
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        fontSize: '12px',
                        fontWeight: '500',
                        borderRadius: '9999px',
                        background: run.status === 'completed' ? '#dcfce7' : run.status === 'running' ? '#fef9c3' : run.status === 'failed' ? '#fecaca' : '#f3f4f6',
                        color: run.status === 'completed' ? '#166534' : run.status === 'running' ? '#854d0e' : run.status === 'failed' ? '#991b1b' : '#374151',
                      }}>
                        {run.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-secondary)' }}>{run.mode}</td>
                    <td style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-secondary)' }}>
                      {run.duration_ms ? `${run.duration_ms}ms` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
