import { useState, useEffect, useCallback } from 'react'
import { api } from '../../lib/api'
import { Badge } from './ui'

const FOLDER_ICONS = {
  docs: { icon: DocsIcon, color: 'text-violet-400', bg: 'bg-violet-500/20' },
  workflow: { icon: WorkflowIcon, color: 'text-amber-400', bg: 'bg-amber-500/20' },
  project: { icon: ProjectIcon, color: 'text-teal-400', bg: 'bg-teal-500/20' },
}

const FILE_ICONS = {
  '.md': { icon: MarkdownIcon, color: 'text-slate-400' },
  '.py': { icon: CodeIcon, color: 'text-blue-400' },
  '.js': { icon: CodeIcon, color: 'text-yellow-400' },
  '.ts': { icon: CodeIcon, color: 'text-blue-400' },
  '.json': { icon: CodeIcon, color: 'text-amber-400' },
  '.yaml': { icon: CodeIcon, color: 'text-amber-400' },
  '.yml': { icon: CodeIcon, color: 'text-amber-400' },
}

export function FileExplorer({ onFileSelect }) {
  const [folders, setFolders] = useState([])
  const [activeFolder, setActiveFolder] = useState('docs')
  const [files, setFiles] = useState([])
  const [currentPath, setCurrentPath] = useState('')
  const [breadcrumbs, setBreadcrumbs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedDirs, setExpandedDirs] = useState(new Set())

  useEffect(() => {
    loadWorkspacePaths()
  }, [])

  useEffect(() => {
    loadFiles(activeFolder, '')
  }, [activeFolder])

  const loadWorkspacePaths = async () => {
    try {
      const paths = await api.workspacePaths()
      setFolders(Object.entries(paths).map(([key, value]) => ({ key, ...value })))
      if (paths.docs?.exists) setActiveFolder('docs')
      else if (paths.workflow?.exists) setActiveFolder('workflow')
      else if (paths.project?.exists) setActiveFolder('project')
    } catch (error) {
      console.error('Failed to load workspace paths:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadFiles = async (folder, path) => {
    setLoading(true)
    try {
      const data = await api.workspaceFiles(folder, path)
      setFiles(data.files || [])
      setCurrentPath(path)
      updateBreadcrumbs(folder, path)
    } catch (error) {
      console.error('Failed to load files:', error)
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  const updateBreadcrumbs = (folder, path) => {
    const parts = path ? path.split('/').filter(Boolean) : []
    const crumbs = [{ label: folder, path: '' }]
    let current = ''
    for (const part of parts) {
      current += (current ? '/' : '') + part
      crumbs.push({ label: part, path: current })
    }
    setBreadcrumbs(crumbs)
  }

  const handleFolderClick = (folderKey) => {
    setActiveFolder(folderKey)
    setCurrentPath('')
    setExpandedDirs(new Set())
  }

  const handleItemClick = (item) => {
    if (item.is_dir) {
      loadFiles(activeFolder, item.path)
      setExpandedDirs(prev => new Set([...prev, item.path]))
    } else {
      onFileSelect?.({ folder: activeFolder, path: item.path, name: item.name })
    }
  }

  const handleBreadcrumbClick = (path) => {
    loadFiles(activeFolder, path)
  }

  const goBack = () => {
    const parts = currentPath.split('/').filter(Boolean)
    parts.pop()
    loadFiles(activeFolder, parts.join('/'))
  }

  const sortedFiles = [...files].sort((a, b) => {
    if (a.is_dir && !b.is_dir) return -1
    if (!a.is_dir && b.is_dir) return 1
    return a.name.localeCompare(b.name)
  })

  if (loading && folders.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin w-6 h-6 border-2 border-accent border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-slate-950">
      {/* Folder tabs */}
      <div className="flex border-b border-slate-800">
        {folders.map((folder) => {
          const config = FOLDER_ICONS[folder.key] || FOLDER_ICONS.docs
          const Icon = config.icon
          return (
            <button
              key={folder.key}
              onClick={() => handleFolderClick(folder.key)}
              className={`
                flex-1 flex items-center justify-center gap-2 px-3 py-3 text-sm font-medium
                transition-colors border-b-2
                ${activeFolder === folder.key
                  ? 'border-accent text-accent bg-accent/5'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
                }
              `}
            >
              <Icon className={`w-4 h-4 ${config.color}`} />
              <span className="hidden lg:inline">{folder.label}</span>
            </button>
          )
        })}
      </div>

      {/* Breadcrumbs */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-slate-800 text-xs">
        <button
          onClick={goBack}
          disabled={!currentPath}
          className="text-slate-500 hover:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <BackIcon className="w-4 h-4" />
        </button>
        <span className="text-slate-600 mx-1">/</span>
        {breadcrumbs.map((crumb, idx) => (
          <span key={idx} className="flex items-center">
            <button
              onClick={() => handleBreadcrumbClick(crumb.path)}
              className={`
                hover:text-slate-200
                ${idx === breadcrumbs.length - 1 ? 'text-slate-300 font-medium' : 'text-slate-500'}
              `}
            >
              {crumb.label}
            </button>
            {idx < breadcrumbs.length - 1 && (
              <span className="text-slate-600 mx-1">/</span>
            )}
          </span>
        ))}
        <button
          onClick={() => loadFiles(activeFolder, currentPath)}
          className="ml-auto p-1 text-slate-500 hover:text-slate-300 transition-colors"
          title="Reload"
        >
          <RefreshIcon className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* File list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin w-5 h-5 border-2 border-accent border-t-transparent rounded-full" />
          </div>
        ) : sortedFiles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-slate-500">
            <FolderEmptyIcon className="w-8 h-8 mb-2" />
            <span className="text-sm">Empty folder</span>
          </div>
        ) : (
          sortedFiles.map((item) => (
            <button
              key={item.path}
              onClick={() => handleItemClick(item)}
              className="w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-800/50 transition-colors text-left"
            >
              {item.is_dir ? (
                <FolderIcon className="w-4 h-4 text-amber-400 flex-shrink-0" />
              ) : (
                <FileTypeIcon file={item} className="w-4 h-4 flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm truncate ${item.is_dir ? 'text-slate-200' : 'text-slate-300'}`}>
                  {item.name}
                </p>
              </div>
              {item.is_dir && (
                <ChevronIcon className="w-4 h-4 text-slate-600" />
              )}
              {item.size > 0 && (
                <span className="text-xs text-slate-600">{formatSize(item.size)}</span>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

function FileTypeIcon({ file, className }) {
  const icon = FILE_ICONS[file.extension] || { icon: FileIcon, color: 'text-slate-400' }
  const Icon = icon.icon
  return <Icon className={`${className} ${icon.color}`} />
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function FolderIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
    </svg>
  )
}

function FileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function CodeIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </svg>
  )
}

function MarkdownIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <path d="M7 15V9l2.5 3L12 9v6" />
      <path d="M17 9v6h-3" />
    </svg>
  )
}

function DocsIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  )
}

function WorkflowIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v6m0 6v10M1 12h6m6 0h10" />
      <path d="M4.22 4.22l4.24 4.24m7.08 7.08l4.24 4.24M4.22 19.78l4.24-4.24m7.08-7.08l4.24-4.24" />
    </svg>
  )
}

function ProjectIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
      <line x1="9" y1="14" x2="15" y2="14" />
    </svg>
  )
}

function BackIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  )
}

function ChevronIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 18l6-6-6-6" />
    </svg>
  )
}

function FolderEmptyIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
    </svg>
  )
}

function RefreshIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </svg>
  )
}
