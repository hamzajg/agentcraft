import { useState, useEffect, useCallback } from 'react'
import { api } from '../../lib/api'
import { Badge, Button } from './ui'

export function FileViewer({ file, onClose }) {
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [viewMode, setViewMode] = useState('content')

  useEffect(() => {
    if (file) {
      loadFile()
    }
    return () => setContent(null)
  }, [file])

  const loadFile = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.readFile(file.folder, file.path)
      setContent(data)
    } catch (err) {
      setError(err.message || 'Failed to load file')
      console.error('Failed to load file:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!file) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500">
        <FileEmptyIcon className="w-12 h-12 mb-4" />
        <p className="text-sm">Select a file to view its contents</p>
      </div>
    )
  }

  const getLanguage = (filename) => {
    const ext = filename.split('.').pop()?.toLowerCase()
    const langMap = {
      'md': 'markdown',
      'py': 'python',
      'js': 'javascript',
      'ts': 'typescript',
      'jsx': 'jsx',
      'tsx': 'tsx',
      'json': 'json',
      'yaml': 'yaml',
      'yml': 'yaml',
      'sh': 'bash',
      'sql': 'sql',
    }
    return langMap[ext] || 'text'
  }

  const isMarkdown = file.name.endsWith('.md')

  return (
    <div className="h-full flex flex-col bg-slate-950">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-3 min-w-0">
          <FileIcon className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
            <p className="text-xs text-slate-500 truncate">{file.path}</p>
          </div>
          {content && (
            <Badge variant="muted" className="flex-shrink-0">
              {content.line_count} lines
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isMarkdown && (
            <div className="flex rounded-lg border border-slate-700 overflow-hidden">
              <button
                onClick={() => setViewMode('content')}
                className={`px-3 py-1 text-xs ${
                  viewMode === 'content'
                    ? 'bg-slate-700 text-slate-200'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-300'
                }`}
              >
                Content
              </button>
              <button
                onClick={() => setViewMode('preview')}
                className={`px-3 py-1 text-xs ${
                  viewMode === 'preview'
                    ? 'bg-slate-700 text-slate-200'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-300'
                }`}
              >
                Preview
              </button>
            </div>
          )}
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin w-6 h-6 border-2 border-accent border-t-transparent rounded-full" />
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 p-4">
            <ErrorIcon className="w-8 h-8 mb-2 text-danger" />
            <p className="text-sm text-danger">{error}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={loadFile}>
              Retry
            </Button>
          </div>
        )}

        {content && !loading && !error && (
          <>
            {viewMode === 'content' ? (
              <div className="h-full overflow-auto">
                <pre className="p-4 text-sm font-mono text-slate-300 leading-relaxed whitespace-pre-wrap">
                  {content.content}
                </pre>
              </div>
            ) : (
              <div className="h-full overflow-auto p-6 prose prose-invert prose-slate max-w-none">
                <MarkdownPreview content={content.content} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function MarkdownPreview({ content }) {
  const lines = content.split('\n')
  
  const renderInline = (text) => {
    const parts = []
    let remaining = text
    let key = 0
    
    while (remaining.length > 0) {
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
      const codeMatch = remaining.match(/`(.+?)`/)
      
      if (boldMatch && boldMatch.index === 0) {
        parts.push(<strong key={key++}>{boldMatch[1]}</strong>)
        remaining = remaining.slice(boldMatch[0].length)
      } else if (codeMatch && codeMatch.index === 0) {
        parts.push(<code key={key++} className="px-1 py-0.5 bg-slate-800 rounded text-sm">{codeMatch[1]}</code>)
        remaining = remaining.slice(codeMatch[0].length)
      } else {
        const match = boldMatch || codeMatch
        const nextIdx = match ? match.index : remaining.length
        parts.push(remaining.slice(0, nextIdx))
        if (match) remaining = remaining.slice(nextIdx)
        else break
      }
    }
    
    return parts
  }

  let inCodeBlock = false
  let codeContent = []
  let codeLanguage = ''
  const elements = []
  let key = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true
        codeContent = []
        codeLanguage = line.slice(3).trim()
      } else {
        inCodeBlock = false
        elements.push(
          <pre key={key++} className="bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-x-auto my-4">
            <code className="text-sm text-slate-300">{codeContent.join('\n')}</code>
          </pre>
        )
        codeContent = []
      }
      continue
    }

    if (inCodeBlock) {
      codeContent.push(line)
      continue
    }

    if (line.startsWith('# ')) {
      elements.push(<h1 key={key++} className="text-2xl font-bold text-slate-100 mt-6 mb-4 first:mt-0">{line.slice(2)}</h1>)
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={key++} className="text-xl font-bold text-slate-100 mt-6 mb-3">{line.slice(3)}</h2>)
    } else if (line.startsWith('### ')) {
      elements.push(<h3 key={key++} className="text-lg font-semibold text-slate-200 mt-4 mb-2">{line.slice(4)}</h3>)
    } else if (line.startsWith('- ')) {
      elements.push(<li key={key++} className="ml-4 text-slate-300">{renderInline(line.slice(2))}</li>)
    } else if (line.match(/^\d+\. /)) {
      const match = line.match(/^(\d+)\. (.+)/)
      elements.push(
        <div key={key++} className="flex gap-2 ml-4 text-slate-300">
          <span className="text-slate-500">{match[1]}.</span>
          <span>{renderInline(match[2])}</span>
        </div>
      )
    } else if (line.trim() === '') {
      elements.push(<div key={key++} className="h-2" />)
    } else if (line.startsWith('> ')) {
      elements.push(
        <blockquote key={key++} className="border-l-4 border-accent pl-4 italic text-slate-400 my-2">
          {renderInline(line.slice(2))}
        </blockquote>
      )
    } else {
      elements.push(<p key={key++} className="text-slate-300 my-2">{renderInline(line)}</p>)
    }
  }

  return <>{elements}</>
}

function FileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function CloseIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function FileEmptyIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function ErrorIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}
