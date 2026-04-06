import { formatDistanceToNow } from 'date-fns'

export function AgentBubble({ msg, onSuggestionClick, onDismiss }) {
  const isPending = msg.status === 'pending'
  const timeAgo   = formatDistanceToNow(new Date(msg.created_at), { addSuffix: true })

  return (
    <div className="animate-slide-up flex flex-col gap-2 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-2 px-1">
        <span className="font-mono text-xs font-semibold text-accent">
          {msg.agent_label}
        </span>
        <span className="text-[10px] text-muted">{timeAgo}</span>
        {isPending && (
          <span className="flex items-center gap-1 text-[10px] text-amber font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse-slow" />
            waiting
          </span>
        )}
        {!isPending && onDismiss && (
          <button
            onClick={() => onDismiss(msg.id)}
            className="ml-auto text-[10px] text-muted hover:text-gray-300 transition-colors"
          >
            dismiss
          </button>
        )}
      </div>

      {/* Bubble */}
      <div className={`
        bg-panel rounded-xl rounded-tl-sm border px-4 py-3 space-y-2.5
        ${isPending ? 'border-amber/40' : 'border-border'}
      `}>
        {/* File pill */}
        {msg.file && (
          <div className="flex items-center gap-1.5 w-fit
                          bg-surface border border-border rounded-md px-2 py-0.5">
            <FileIcon />
            <span className="font-mono text-[11px] text-gray-400 truncate max-w-xs">
              {msg.file}
            </span>
          </div>
        )}

        {/* Question */}
        <p className="text-sm text-gray-200 leading-relaxed">{msg.question}</p>

        {/* Partial output */}
        {msg.partial_output && (
          <details className="group">
            <summary className="text-[11px] text-muted cursor-pointer select-none
                               hover:text-gray-400 transition-colors list-none flex items-center gap-1">
              <ChevronIcon className="w-3 h-3 transition-transform group-open:rotate-90" />
              Partial output
            </summary>
            <pre className="mt-2 text-[11px] font-mono text-gray-400 bg-surface
                            rounded-lg p-3 overflow-x-auto whitespace-pre-wrap max-h-40
                            border border-border">
              {msg.partial_output}
            </pre>
          </details>
        )}

        {/* Suggestion chips — only for pending */}
        {isPending && msg.suggestions?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {msg.suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => onSuggestionClick(s)}
                className="text-xs px-3 py-1 rounded-full border border-accent/60
                           text-accent hover:bg-accent-dim transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Replied indicator */}
        {msg.status === 'replied' && msg.reply && (
          <div className="flex items-center gap-1.5 text-[11px] text-teal border-t border-border pt-2 mt-1">
            <CheckIcon />
            <span>Replied · agent resumed</span>
          </div>
        )}
      </div>
    </div>
  )
}

export function YouBubble({ msg }) {
  const timeAgo = formatDistanceToNow(new Date(msg.replied_at), { addSuffix: true })
  return (
    <div className="animate-slide-up flex flex-col items-end gap-1 max-w-2xl ml-auto">
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-muted">{timeAgo}</span>
        <span className="font-mono text-xs font-semibold text-teal">You</span>
      </div>
      <div className="bg-teal-dim border border-teal/30 rounded-xl rounded-tr-sm px-4 py-2.5">
        <p className="text-sm text-gray-200 leading-relaxed">{msg.reply}</p>
      </div>
    </div>
  )
}

// ── Micro icons ───────────────────────────────────────────────────────────────

function FileIcon() {
  return (
    <svg className="w-3 h-3 text-muted flex-shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 2H4a1 1 0 00-1 1v10a1 1 0 001 1h8a1 1 0 001-1V6L9 2z" />
      <path d="M9 2v4h4" />
    </svg>
  )
}

function ChevronIcon({ className }) {
  return (
    <svg className={className ?? 'w-4 h-4'} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 4l4 4-4 4" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 8l4 4 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
