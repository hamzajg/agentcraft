import { useState, useRef, useEffect } from 'react'

function MessageBubble({ msg }) {
  const isUser = msg.message_type === 'user'
  const isTool = msg.message_type === 'tool_call' || msg.message_type === 'tool_result'
  const isSystem = msg.message_type === 'system'

  return (
    <div style={{
      display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start',
      padding: '4px 16px', maxWidth: '100%',
    }}>
      <div style={{
        maxWidth: '80%', padding: '10px 14px', borderRadius: 12,
        background: isUser
          ? 'var(--accent-primary)'
          : isTool
            ? 'var(--bg-elevated)'
            : isSystem
              ? 'var(--bg-tertiary)'
              : 'var(--bg-secondary)',
        color: isUser ? '#000' : 'var(--text-primary)',
        fontSize: 13, lineHeight: 1.5,
        border: isUser ? 'none' : '1px solid var(--border-subtle)',
      }}>
        {isTool && (
          <div style={{
            fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
            color: msg.message_type === 'tool_call' ? 'var(--warning)' : 'var(--success)',
            marginBottom: 4,
          }}>
            {msg.message_type === 'tool_call' ? 'Tool Call' : 'Tool Result'}
          </div>
        )}
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {msg.content}
        </div>
        {msg.tool_name && (
          <div style={{
            marginTop: 6, padding: '4px 8px', borderRadius: 4,
            background: 'var(--bg-tertiary)', fontSize: 11, fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
          }}>
            {msg.tool_name}({JSON.stringify(msg.tool_args || {}).slice(0, 80)}...)
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatArea({ agent, conversation, messages, onSendMessage, onToggleArtifacts, showArtifacts, artifactCount }) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || sending) return
    const content = input.trim()
    setInput('')
    setSending(true)
    try {
      await onSendMessage(content)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (!agent) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
        Select an agent to start chatting
      </div>
    )
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px', borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--bg-secondary)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'var(--bg-elevated)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 600, color: 'var(--accent-primary)',
          }}>
            {agent.name.charAt(0)}
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{agent.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {agent.llm_model} · {conversation?.title || 'No conversation'}
            </div>
          </div>
        </div>
        <button onClick={onToggleArtifacts} style={{
          padding: '6px 12px', borderRadius: 6, fontSize: 12,
          background: showArtifacts ? 'var(--accent-dim)' : 'var(--bg-tertiary)',
          border: `1px solid ${showArtifacts ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
          color: showArtifacts ? 'var(--accent-primary)' : 'var(--text-secondary)',
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{ fontSize: 14 }}>&#128196;</span>
          Artifacts {artifactCount > 0 && <span style={{ fontSize: 10, background: 'var(--accent-dim)', padding: '1px 5px', borderRadius: 3 }}>{artifactCount}</span>}
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 0' }}>
        {messages.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--text-tertiary)',
          }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>&#129302;</div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Start a conversation</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>Type a message below to begin</div>
          </div>
        )}
        {messages.map(msg => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message... (Enter to send, Shift+Enter for newline)"
            rows={1}
            style={{
              flex: 1, padding: '10px 14px', borderRadius: 8,
              border: '1px solid var(--border-subtle)', background: 'var(--bg-tertiary)',
              color: 'var(--text-primary)', fontSize: 13, resize: 'none',
              outline: 'none', fontFamily: 'var(--font-body)',
              minHeight: 40, maxHeight: 120,
            }}
          />
          <button onClick={handleSend} disabled={!input.trim() || sending} style={{
            padding: '10px 16px', borderRadius: 8,
            background: input.trim() && !sending ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
            color: input.trim() && !sending ? '#000' : 'var(--text-tertiary)',
            border: 'none', cursor: input.trim() && !sending ? 'pointer' : 'default',
            fontSize: 13, fontWeight: 500,
          }}>
            {sending ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}
