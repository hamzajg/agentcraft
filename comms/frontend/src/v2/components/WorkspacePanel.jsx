import { Card, CardBody, CardHeader, Badge, Button, Input } from './ui'

export function WorkspacePanel({ context = {}, files = [], onFileClick }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-100">Context Store</h3>
            <Badge variant="muted">{Object.keys(context).length} keys</Badge>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="divide-y divide-slate-800">
            {Object.entries(context).map(([key, value]) => (
              <div key={key} className="px-5 py-3 flex items-start gap-4">
                <code className="text-xs text-accent font-mono w-32 flex-shrink-0">{key}</code>
                <code className="text-xs text-slate-400 font-mono truncate">
                  {typeof value === 'object' ? JSON.stringify(value).slice(0, 100) : String(value)}
                </code>
              </div>
            ))}
            {Object.keys(context).length === 0 && (
              <div className="px-5 py-8 text-center text-sm text-slate-500">
                No context entries yet
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-100">Workspace Files</h3>
            <Badge variant="muted">{files.length} files</Badge>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="divide-y divide-slate-800">
            {files.map((file, idx) => (
              <button
                key={idx}
                onClick={() => onFileClick?.(file)}
                className="w-full px-5 py-3 flex items-center gap-3 hover:bg-slate-800/30 transition-colors text-left"
              >
                <FileIcon className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-300 truncate font-mono">{file.path || file}</p>
                  {file.modified && (
                    <p className="text-xs text-slate-500 mt-0.5">
                      Modified {formatTimeAgo(file.modified)}
                    </p>
                  )}
                </div>
              </button>
            ))}
            {files.length === 0 && (
              <div className="px-5 py-8 text-center text-sm text-slate-500">
                No files in workspace yet
              </div>
            )}
          </div>
        </CardBody>
      </Card>
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

function FileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  )
}
