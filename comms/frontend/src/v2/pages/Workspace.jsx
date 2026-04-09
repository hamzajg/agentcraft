import { useState, useMemo } from 'react'
import { Card, CardBody, Badge, Button, Input } from '../components/ui'
import { WorkspacePanel } from '../components/WorkspacePanel'
import { api } from '../../lib/api';

export function Workspace({ events = [] }) {
  const [context, setContext] = useState({})
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)

  const workspaceFiles = useMemo(() => {
    return events
      .filter(e => e.type === 'file_written' || e.type === 'file_modified')
      .map((e, idx) => ({
        path: e.content?.path || e.file || `File ${idx + 1}`,
        modified: e.time,
        type: e.type,
      }))
  }, [events])

  const contextEntries = useMemo(() => {
    const entries = {}
    events
      .filter(e => e.type === 'agent_context')
      .forEach(e => {
        if (e.content?.key) {
          entries[e.content.key] = e.content.value || e.content
        }
      })
    return entries
  }, [events])

  const handleRefresh = async () => {
    setLoading(true)
    try {
      const stats = await api.stats()
      setContext(stats.context || {})
      setFiles(stats.files || workspaceFiles)
    } catch (error) {
      console.error('Failed to refresh workspace:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Workspace</h1>
          <p className="text-sm text-slate-400 mt-1">Files and context shared between agents</p>
        </div>
        <Button variant="secondary" size="sm" onClick={handleRefresh} disabled={loading}>
          <RefreshIcon className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        <div className="space-y-6">
          <Card>
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="font-semibold text-slate-100">Project Files</h2>
              <Badge variant="muted">{workspaceFiles.length} files</Badge>
            </div>
            <CardBody className="p-0">
              {workspaceFiles.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-12 h-12 rounded-xl bg-slate-800 mx-auto mb-4 flex items-center justify-center">
                    <FolderIcon className="w-6 h-6 text-slate-600" />
                  </div>
                  <h3 className="text-lg font-medium text-slate-400">No files yet</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    Files will appear here as agents create them
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-slate-800">
                  {workspaceFiles.map((file, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedFile(file)}
                      className={`
                        w-full flex items-center gap-4 px-5 py-4 hover:bg-slate-800/30 transition-colors text-left
                        ${selectedFile === file ? 'bg-accent/5 border-l-2 border-accent' : ''}
                      `}
                    >
                      <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center flex-shrink-0">
                        <FileIcon className="w-5 h-5 text-slate-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-200 truncate font-mono">
                          {file.path}
                        </p>
                        {file.modified && (
                          <p className="text-xs text-slate-500 mt-1">
                            Modified {formatTimeAgo(file.modified)}
                          </p>
                        )}
                      </div>
                      <Badge variant="muted">{file.type?.replace('_', ' ') || 'file'}</Badge>
                    </button>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {selectedFile && (
            <Card>
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileIcon className="w-5 h-5 text-slate-400" />
                  <h2 className="font-semibold text-slate-100 font-mono text-sm truncate">
                    {selectedFile.path}
                  </h2>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setSelectedFile(null)}>
                  <CloseIcon className="w-4 h-4" />
                </Button>
              </div>
              <CardBody className="p-0">
                <pre className="p-5 text-sm text-slate-300 font-mono overflow-x-auto max-h-96 bg-slate-950">
                  {selectedFile.content || '// File content will appear here'}
                </pre>
              </CardBody>
            </Card>
          )}
        </div>

        <WorkspacePanel context={contextEntries} files={workspaceFiles} />
      </div>
    </div>
  )
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return ''
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function RefreshIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  )
}

function FolderIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function FileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  )
}

function CloseIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
