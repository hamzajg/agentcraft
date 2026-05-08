import { useState } from 'react'
import { BookOpenIcon, ChartIcon, WifiIcon } from './icons'

export function RAGPanel() {
  const [documents] = useState([
    { id: 1, name: 'Architecture.md', size: '12KB', status: 'indexed', date: '2024-01-15' },
    { id: 2, name: 'API-Reference.md', size: '45KB', status: 'indexed', date: '2024-01-14' },
    { id: 3, name: 'Requirements.pdf', size: '128KB', status: 'processing', date: '2024-01-13' },
  ])

  return (
    <div className="flex-1 flex flex-col p-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BookOpenIcon className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
          <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Knowledge Base</h2>
        </div>
        <button 
          className="px-4 py-2 rounded text-sm font-medium"
          style={{ background: 'var(--accent-primary)', color: 'var(--bg-primary)' }}
        >
          + Upload Document
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <StatCard icon={BookOpenIcon} label="Total Documents" value="24" />
        <StatCard icon={ChartIcon} label="Indexed Chunks" value="1,284" />
        <StatCard icon={WifiIcon} label="Last Updated" value="2 min ago" />
      </div>

      <div 
        className="flex-1 rounded-lg overflow-hidden"
        style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
      >
        <table className="w-full">
          <thead style={{ background: 'var(--bg-tertiary)' }}>
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Document</th>
              <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Size</th>
              <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {documents.map(doc => (
              <tr key={doc.id} className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-primary)' }}>{doc.name}</td>
                <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>{doc.size}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={doc.status} />
                </td>
                <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-tertiary)' }}>{doc.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div 
      className="p-4 rounded-lg"
      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <Icon className="w-5 h-5 mb-2" style={{ color: 'var(--accent-primary)' }} />
      <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</div>
      <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</div>
    </div>
  )
}

function StatusBadge({ status }) {
  const styles = {
    indexed: { background: 'var(--success)', color: 'var(--bg-primary)' },
    processing: { background: 'var(--warning)', color: 'var(--bg-primary)' },
  }
  
  return (
    <span 
      className="px-2 py-1 rounded text-xs font-medium"
      style={styles[status] || styles.processing}
    >
      {status}
    </span>
  )
}
