import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Badge, Avatar } from './ui';
import { formatTime, formatRelativeTime } from '../utils/formatTime';

const PAGE = 15;

/* ─────────────────────────────────────────────────────────
   AgentPanel Redesigned - Modern Chat Interface
   Features:
   • Modern message bubbles with better visual hierarchy
   • Enhanced input area with improved UX
   • Smooth transitions and micro-interactions
   • Better agent status visualization
   • Improved file attachment handling
   ───────────────────────────────────────────────────────── */

export function AgentPanelRedesigned({ channels, statuses, messages, activeAgent, setActiveAgent, sending, onReply, busMessages = [], isCollapsed, setIsCollapsed }) {
  const [showChat, setShowChat] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [localReplies, setLocalReplies] = useState({});
  const [showBus, setShowBus] = useState(false);
  const [unreadBus, setUnreadBus] = useState(0);
  const [seenBusIds, setSeenBusIds] = useState(new Set());
  const [isTyping, setIsTyping] = useState(false);
  const [showFloatingChat, setShowFloatingChat] = useState(false);

  // Older-message pagination
  const [history, setHistory] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [cursor, setCursor] = useState(null);
  const [loading, setLoading] = useState(false);

  // Scroll tracking
  const [atBottom, setAtBottom] = useState(true);
  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const topRef = useRef(null);
  const storeLenRef = useRef(0);

  const selected = channels.find(c => c.agent_id === activeAgent);

  // WebSocket store messages
  const store = useMemo(() => {
    if (!activeAgent) return [];
    return (messages[activeAgent] ?? [])
      .slice()
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }, [activeAgent, messages]);

  // Latest pending message
  const pending = useMemo(() => {
    const p = store.filter(m => m.status === 'pending');
    return p.length ? p.reduce((a, b) => new Date(b.created_at) > new Date(a.created_at) ? b : a) : null;
  }, [store]);

  // Merge history + store
  const all = useMemo(() => {
    const m = new Map();
    for (const x of history) m.set(x.id, x);
    for (const x of store) m.set(x.id, x);
    return [...m.values()].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }, [history, store]);

  // Agent-to-agent bus messages
  const busMsgs = useMemo(() => {
    if (!activeAgent) return [];
    return busMessages
      .filter(m => m.from_agent === activeAgent || m.to_agent === activeAgent)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [activeAgent, busMessages]);

  useEffect(() => {
    if (!activeAgent) return;
    const newOnes = busMsgs.filter(m => !seenBusIds.has(m.id)).length;
    setUnreadBus(newOnes);
  }, [busMsgs.length, activeAgent, seenBusIds]);

  const markBus = useCallback(() => {
    const s = new Set(seenBusIds);
    busMsgs.forEach(m => s.add(m.id));
    setSeenBusIds(s);
    setUnreadBus(0);
  }, [busMsgs, seenBusIds]);

  // Load older messages
  const loadOlder = useCallback(async () => {
    if (loading || !hasMore || !activeAgent) return;
    setLoading(true);
    try {
      const url = new URL(`/api/messages/${activeAgent}/older`, location.origin);
      url.searchParams.set('limit', String(PAGE));
      if (cursor) url.searchParams.set('before', cursor);

      const res = await fetch(url);
      const data = await res.json();
      if (!data.length || data.length < PAGE) setHasMore(false);
      if (data.length) {
        const chrono = [...data].reverse();
        setHistory(prev => [...chrono, ...prev]);
        setCursor(new Date(chrono[0].created_at));
      }
    } catch (e) {
      console.error('loadOlder', e);
    } finally {
      setLoading(false);
    }
  }, [loading, hasMore, activeAgent, cursor]);

  // Scroll handling
  const onScroll = useCallback((e) => {
    const el = e.target;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    setAtBottom(isAtBottom);
    
    if (el.scrollTop < 100 && hasMore && !loading) {
      loadOlder();
    }
  }, [hasMore, loading, loadOlder]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (atBottom && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [all.length, atBottom]);

  // Navigation functions
  const goBack = useCallback(() => {
    setShowChat(false);
    setReplyText('');
  }, []);

  const pickAgent = useCallback((agentId) => {
    setActiveAgent(agentId);
    setShowChat(true);
  }, [setActiveAgent]);

  const sendReply = useCallback(() => {
    if (!replyText.trim() || sending) return;
    const reply = replyText.trim();
    setLocalReplies(prev => ({ ...prev, [pending.id]: reply }));
    onReply(pending.id, reply);
    setReplyText('');
    setIsTyping(false);
  }, [replyText, sending, pending, onReply]);

  const onKey = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendReply();
    }
  }, [sendReply]);

  const tapSuggestion = useCallback((suggestion, msgId) => {
    setReplyText(suggestion);
    setIsTyping(true);
  }, []);

  const handleInputChange = useCallback((e) => {
    setReplyText(e.target.value);
    setIsTyping(e.target.value.length > 0);
  }, []);

  // Collapse/expand functionality
  const toggleCollapse = useCallback(() => {
    setIsCollapsed(prev => !prev);
    if (!isCollapsed && activeAgent) {
      setShowFloatingChat(true);
    } else {
      setShowFloatingChat(false);
    }
  }, [isCollapsed, activeAgent, setIsCollapsed]);

  const selectAgentFromCollapsed = useCallback((agentId) => {
    setActiveAgent(agentId);
    setIsCollapsed(false);
    setShowChat(true);
    setShowFloatingChat(false);
  }, [setActiveAgent, setIsCollapsed]);

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-primary)' }}>
      {/* Collapsed State - Avatar Bar */}
      {isCollapsed && (
        <CollapsedAvatarBar
          channels={channels}
          statuses={statuses}
          messages={messages}
          activeAgent={activeAgent}
          busMessages={busMessages}
          seenBusIds={seenBusIds}
          onSelect={selectAgentFromCollapsed}
          onExpand={() => setIsCollapsed(false)}
        />
      )}

      {/* Expanded State */}
      {!isCollapsed && (
        <>
          {/* Header */}
          <HeaderRowRedesigned
            showChat={showChat}
            channels={channels}
            statuses={statuses}
            pending={pending}
            selected={selected}
            activeAgent={activeAgent}
            status={statuses[activeAgent]}
            unreadBus={unreadBus}
            showBus={showBus}
            onBack={goBack}
            onBusToggle={() => setShowBus(p => { const n = !p; if (n) markBus(); return n; })}
            onCollapse={toggleCollapse}
          />

          {/* Agent List */}
          {!showChat && (
            <AgentListRedesigned
              channels={channels}
              statuses={statuses}
              messages={messages}
              activeAgent={activeAgent}
              busMessages={busMessages}
              seenBusIds={seenBusIds}
              onSelect={pickAgent}
            />
          )}

          {/* Chat View */}
          {showChat && activeAgent && (
            <>
              {/* Scroll container */}
              <div 
                ref={containerRef} 
                onScroll={onScroll}
                className="flex-1 overflow-y-auto px-4 py-4"
                style={{ background: 'linear-gradient(to bottom, var(--bg-primary), var(--bg-secondary))' }}
              >
                {/* Top sentinel */}
                <div ref={topRef} className="h-0" />

                {/* Loading indicator */}
                {loading && (
                  <div className="flex items-center justify-center py-4">
                    <LoadingSpinner />
                    <span className="ml-3 text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading older messages...</span>
                  </div>
                )}

                {/* Bus messages */}
                {showBus && busMsgs.length > 0 && (
                  <BusPanelRedesigned msgs={busMsgs} />
                )}

                {/* Empty state */}
                {!all.length && (
                  <EmptyChatState pending={!!pending} />
                )}

                {/* Messages */}
                {all.map((msg, index) => {
                  const isPending = msg.id === pending?.id;
                  const reply = localReplies[msg.id] || msg.reply;
                  const showDate = index === 0 || new Date(msg.created_at).toDateString() !== new Date(all[index - 1].created_at).toDateString();
                  
                  return (
                    <div key={msg.id}>
                      {showDate && <DateSeparator date={msg.created_at} />}
                      <MessageBubbleRedesigned
                        msg={msg}
                        isPending={isPending}
                        reply={reply}
                        suggestions={msg.suggestions}
                        sending={sending}
                        onSuggest={s => tapSuggestion(s, msg.id)}
                        isTyping={isTyping}
                      />
                    </div>
                  );
                })}

                {/* Bottom anchor */}
                <div ref={bottomRef} className="h-0" />
              </div>

              {/* Reply Bar */}
              <ReplyBarRedesigned
                replyText={replyText}
                setReplyText={setReplyText}
                onInputChange={handleInputChange}
                onKeyDown={onKey}
                hasPending={!!pending}
                agentId={activeAgent}
                sending={sending}
                onSend={sendReply}
                isTyping={isTyping}
              />
            </>
          )}
        </>
      )}

      {/* Floating Chat (when collapsed and agent selected) */}
      {isCollapsed && activeAgent && showFloatingChat && (
        <FloatingChatBox
          agentId={activeAgent}
          channels={channels}
          statuses={statuses}
          messages={messages}
          pending={pending}
          sending={sending}
          onReply={onReply}
          onClose={() => setShowFloatingChat(false)}
        />
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════
   Redesigned Sub-components
   ═══════════════════════════════════════════ */

function HeaderRowRedesigned({ showChat, channels, statuses, pending, selected, activeAgent, status, unreadBus, showBus, onBack, onBusToggle, onCollapse }) {
  const agentCount = channels.length;
  const activeAgents = Object.entries(statuses).filter(([, s]) => s === 'running').length;
  const blockedAgents = Object.entries(statuses).filter(([, s]) => s === 'blocked').length;
  const idleAgents = agentCount - activeAgents - blockedAgents;

  return (
    <div 
      className="px-4 py-3 border-b flex items-center justify-between"
      style={{ 
        background: 'var(--bg-secondary)', 
        borderColor: 'var(--border-subtle)',
        backdropFilter: 'blur(8px)'
      }}
    >
      {showChat ? (
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg transition-all duration-200 hover:scale-105"
            style={{ 
              background: 'var(--bg-tertiary)', 
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)'
            }}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          
          <div className="flex items-center gap-3">
            <Avatar name={selected?.agent_id} size="sm" />
            <div>
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {selected?.agent_id}
              </div>
              <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                {status === 'running' ? 'Active' : status === 'blocked' ? 'Blocked' : 'Idle'}
              </div>
            </div>
          </div>

          {pending && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium animate-pulse"
              style={{ 
                background: 'var(--accent-primary)', 
                color: 'var(--bg-primary)' 
              }}
            >
              <span className="w-2 h-2 rounded-full bg-white" />
              Pending Reply
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Agents
          </h2>
          <div className="flex items-center gap-4 text-sm">
            <StatusPill label="Active" count={activeAgents} color="var(--success)" />
            <StatusPill label="Blocked" count={blockedAgents} color="var(--warning)" />
            <StatusPill label="Idle" count={idleAgents} color="var(--text-tertiary)" />
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        {showChat && unreadBus > 0 && (
          <button
            onClick={onBusToggle}
            className="relative p-2 rounded-lg transition-all duration-200 hover:scale-105"
            style={{ 
              background: 'var(--bg-tertiary)', 
              border: '1px solid var(--border-subtle)'
            }}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <path d="M22 6l-4 4 4 4V6z" />
            </svg>
            <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center"
              style={{ 
                background: 'var(--accent-primary)', 
                color: 'var(--bg-primary)',
                fontSize: '10px'
              }}
            >
              {unreadBus > 99 ? '99+' : unreadBus}
            </span>
          </button>
        )}
        
        {/* Collapse button */}
        {onCollapse && (
          <button
            onClick={onCollapse}
            className="p-2 rounded-lg transition-all duration-200 hover:scale-105"
            style={{ 
              background: 'var(--bg-tertiary)', 
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)'
            }}
            title="Collapse Panel"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18l6-6" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

function StatusPill({ label, count, color }) {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
      style={{ 
        background: color + '20', 
        color: color,
        border: `1px solid ${color}40`
      }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label}: {count}
    </div>
  );
}

function MessageBubbleRedesigned({ msg, isPending, reply, suggestions, sending, onSuggest, isTyping }) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  
  return (
    <div className="mb-4 animate-fade-in">
      {/* Agent message */}
      <div className="flex gap-3">
        <Avatar name={msg.agent_id} size="sm" />
        <div className="flex-1 max-w-full">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              @{msg.agent_id}
            </span>
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              {formatRelativeTime(msg.created_at)}
            </span>
            {isPending && !reply && (
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium animate-pulse"
                style={{ 
                  background: 'var(--warning)', 
                  color: 'var(--bg-primary)' 
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                Awaiting Reply
              </span>
            )}
          </div>
          
          <div 
            className="p-4 rounded-xl transition-all duration-200 hover:scale-[1.01]"
            style={{ 
              background: isPending && !reply ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              boxShadow: isPending ? '0 0 0 2px var(--warning)30' : 'none'
            }}
          >
            {msg.question && (
              <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
                {msg.question}
              </p>
            )}
            
            {msg.file && (
              <FileAttachment fileName={msg.file} />
            )}
            
            {suggestions?.length > 0 && isPending && !reply && (
              <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
                    Quick Replies
                  </span>
                  <button
                    onClick={() => setShowSuggestions(!showSuggestions)}
                    className="text-xs p-1 rounded transition-colors"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d={showSuggestions ? "M6 9l6 6 6-6" : "M6 15l6-6 6 6"} />
                    </svg>
                  </button>
                </div>
                
                {showSuggestions && (
                  <div className="grid grid-cols-1 gap-2">
                    {suggestions.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => onSuggest(s)}
                        disabled={sending}
                        className="text-left p-3 rounded-lg text-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
                        style={{
                          background: 'var(--bg-tertiary)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-secondary)',
                          opacity: sending ? 0.6 : 1
                        }}
                      >
                        {s.length > 60 ? s.slice(0, 60) + '…' : s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* User reply */}
      {reply && (
        <div className="flex gap-3 mt-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: 'var(--accent-primary)', color: 'var(--bg-primary)' }}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-medium" style={{ color: 'var(--accent-primary)' }}>
                You
              </span>
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                {formatRelativeTime(msg.replied_at || msg.created_at)}
              </span>
            </div>
            <div 
              className="p-4 rounded-xl"
              style={{ 
                background: 'var(--accent-primary)10', 
                border: '1px solid var(--accent-primary)30' 
              }}
            >
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {reply}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FileAttachment({ fileName }) {
  return (
    <div className="flex items-center gap-2.5 p-2.5 rounded-lg mt-2"
      style={{ 
        background: 'var(--bg-tertiary)', 
        border: '1px solid var(--border-subtle)' 
      }}
    >
      <div className="w-8 h-8 rounded flex items-center justify-center"
        style={{ background: 'var(--accent-primary)20', color: 'var(--accent-primary)' }}
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14,2 14,8 20,8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
          {fileName}
        </p>
      </div>
    </div>
  );
}

function ReplyBarRedesigned({ replyText, setReplyText, onInputChange, onKeyDown, hasPending, agentId, sending, onSend, isTyping }) {
  const textareaRef = useRef(null);
  
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [replyText]);

  return (
    <div 
      className="border-t p-4"
      style={{ 
        background: 'var(--bg-secondary)', 
        borderColor: 'var(--border-subtle)',
        backdropFilter: 'blur(8px)'
      }}
    >
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={replyText}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            placeholder={hasPending ? 'Type your reply...' : 'No pending requests'}
            disabled={!hasPending || sending}
            rows={1}
            className="w-full px-4 py-3 rounded-xl resize-none transition-all duration-200"
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
              fontSize: '14px',
              lineHeight: '1.5',
              opacity: (!hasPending || sending) ? 0.6 : 1,
              boxShadow: isTyping ? '0 0 0 3px var(--accent-primary)20' : 'none'
            }}
          />
          <div className="absolute right-3 bottom-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {hasPending ? `Replying to @${agentId}` : 'Idle'}
          </div>
        </div>
        
        <button
          onClick={onSend}
          disabled={!hasPending || !replyText.trim() || sending}
          className="px-6 py-3 rounded-xl font-medium transition-all duration-200 flex items-center gap-2"
          style={{
            background: (!hasPending || !replyText.trim() || sending) ? 'var(--bg-tertiary)' : 'var(--accent-primary)',
            color: (!hasPending || !replyText.trim() || sending) ? 'var(--text-tertiary)' : 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            opacity: (!hasPending || !replyText.trim() || sending) ? 0.6 : 1,
            transform: sending ? 'scale(0.95)' : 'scale(1)'
          }}
        >
          {sending ? (
            <>
              <LoadingSpinner size="small" />
              Sending...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22,2 15,22 11,13" />
                <circle cx="10" cy="14" r="8" />
              </svg>
              Send
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function AgentListRedesigned({ channels, statuses, messages, activeAgent, busMessages, seenBusIds, onSelect }) {
  return (
    <div className="p-4">
      <div className="grid grid-cols-1 gap-3">
        {channels.map(channel => {
          const status = statuses[channel.agent_id];
          const msgCount = messages[channel.agent_id]?.length || 0;
          const unreadBus = busMessages.filter(m => 
            (m.from_agent === channel.agent_id || m.to_agent === channel.agent_id) && 
            !seenBusIds.has(m.id)
          ).length;
          
          return (
            <AgentCardRedesigned
              key={channel.agent_id}
              channel={channel}
              status={status}
              msgCount={msgCount}
              unreadBus={unreadBus}
              isActive={activeAgent === channel.agent_id}
              onClick={() => onSelect(channel.agent_id)}
            />
          );
        })}
      </div>
    </div>
  );
}

function AgentCardRedesigned({ channel, status, msgCount, unreadBus, isActive, onClick }) {
  const statusConfig = {
    running: { color: 'var(--success)', label: 'Active', icon: '●' },
    blocked: { color: 'var(--warning)', label: 'Blocked', icon: '■' },
    idle: { color: 'var(--text-tertiary)', label: 'Idle', icon: '○' }
  };
  
  const config = statusConfig[status] || statusConfig.idle;
  
  return (
    <button
      onClick={onClick}
      className="p-4 rounded-xl border transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] text-left w-full"
      style={{
        background: isActive ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
        borderColor: isActive ? 'var(--accent-primary)' : 'var(--border-subtle)',
        borderWidth: isActive ? '2px' : '1px',
        boxShadow: isActive ? '0 0 0 4px var(--accent-primary)20' : 'none'
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <Avatar name={channel.agent_id} size="md" />
          <div>
            <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              {channel.agent_id}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="w-2 h-2 rounded-full" style={{ background: config.color }} />
              <span className="text-xs" style={{ color: config.color }}>
                {config.label}
              </span>
            </div>
          </div>
        </div>
        
        {unreadBus > 0 && (
          <span className="px-2 py-1 rounded-full text-xs font-bold"
            style={{ 
              background: 'var(--accent-primary)', 
              color: 'var(--bg-primary)' 
            }}
          >
            {unreadBus > 9 ? '9+' : unreadBus}
          </span>
        )}
      </div>
      
      <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        <span>{msgCount} messages</span>
        {channel.description && (
          <span className="truncate flex-1">{channel.description}</span>
        )}
      </div>
    </button>
  );
}

function BusPanelRedesigned({ msgs }) {
  return (
    <div className="mb-4 p-3 rounded-xl"
      style={{ 
        background: 'var(--bg-tertiary)', 
        border: '1px solid var(--border-subtle)' 
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
          <path d="M22 6l-4 4 4 4V6z" />
        </svg>
        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Agent Collaboration
        </span>
      </div>
      
      <div className="space-y-2">
        {msgs.slice(0, 10).map(msg => (
          <div key={msg.id} className="flex items-center gap-2 text-xs p-2 rounded"
            style={{ background: 'var(--bg-secondary)' }}
          >
            <span style={{ color: 'var(--text-tertiary)' }}>
              {formatTime(msg.created_at)}
            </span>
            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
              {msg.from_agent} → {msg.to_agent}
            </span>
            <span className="truncate flex-1" style={{ color: 'var(--text-secondary)' }}>
              {msg.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyChatState({ pending }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
        style={{ 
          background: 'var(--bg-tertiary)', 
          border: '2px dashed var(--border-subtle)' 
        }}
      >
        <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
        {pending ? 'New Message' : 'No Messages Yet'}
      </h3>
      <p className="text-sm text-center max-w-md" style={{ color: 'var(--text-tertiary)' }}>
        {pending 
          ? 'Agent has sent you a message. Reply to start the conversation.'
          : 'Start a conversation by selecting an agent from the list.'
        }
      </p>
    </div>
  );
}

function LoadingSpinner({ size = "medium" }) {
  const sizeMap = { small: 16, medium: 20, large: 24 };
  const sizeVal = sizeMap[size] || sizeMap.medium;
  
  return (
    <div className="animate-spin" style={{ width: sizeVal, height: sizeVal }}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 1 18 0" />
      </svg>
    </div>
  );
}

function CollapsedAvatarBar({ channels, statuses, messages, activeAgent, busMessages, seenBusIds, onSelect, onExpand }) {
  return (
    <div 
      className="flex flex-col items-center gap-2 py-3 transition-all duration-300"
      style={{ 
        width: '60px',
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-subtle)',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
      }}
    >
      {/* Expand toggle button */}
      <button
        onClick={onExpand}
        className="p-2 rounded-lg transition-all duration-200 hover:scale-105"
        style={{ 
          background: 'var(--bg-tertiary)', 
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-secondary)'
        }}
        title="Expand Agent Panel"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 18l6-6-6-6" />
        </svg>
      </button>

      {/* Agent avatars */}
      <div className="flex-1 flex flex-col items-center gap-2 overflow-y-auto max-h-full">
        {channels.map(channel => {
          const status = statuses[channel.agent_id];
          const msgCount = messages[channel.agent_id]?.length || 0;
          const unreadBus = busMessages.filter(m => 
            (m.from_agent === channel.agent_id || m.to_agent === channel.agent_id) && 
            !seenBusIds.has(m.id)
          ).length;
          const isActive = activeAgent === channel.agent_id;
          
          return (
            <button
              key={channel.agent_id}
              onClick={() => onSelect(channel.agent_id)}
              className="relative group transition-all duration-200 hover:scale-110"
              title={channel.agent_id}
            >
              <div className="relative">
                <Avatar name={channel.agent_id} size="sm" />
                
                {/* Status indicator */}
                <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 transition-all duration-200"
                  style={{ 
                    background: status === 'running' ? 'var(--success)' : 
                               status === 'blocked' ? 'var(--warning)' : 'var(--text-tertiary)',
                    borderColor: 'var(--bg-secondary)',
                    transform: isActive ? 'scale(125)' : 'scale(100)'
                  }}
                />
                
                {/* Unread badges */}
                {unreadBus > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full text-xs font-bold flex items-center justify-center"
                    style={{ 
                      background: 'var(--accent-primary)', 
                      color: 'var(--bg-primary)',
                      fontSize: '10px',
                      fontWeight: 'bold'
                    }}
                  >
                    {unreadBus > 9 ? '9+' : unreadBus}
                  </span>
                )}
                
                {/* Active indicator */}
                {isActive && (
                  <div className="absolute inset-0 rounded-full border-2"
                    style={{ 
                      borderColor: 'var(--accent-primary)',
                      animation: 'pulse 2s infinite'
                    }}
                  />
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FloatingChatBox({ agentId, channels, statuses, messages, pending, sending, onReply, onClose }) {
  const [replyText, setReplyText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [position, setPosition] = useState({ x: 80, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef(null);
  
  const selected = channels.find(c => c.agent_id === agentId);
  const status = statuses[agentId];
  
  // Messages for this agent
  const store = useMemo(() => {
    return (messages[agentId] ?? [])
      .slice()
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }, [agentId, messages]);

  // Handle drag
  const handleMouseDown = useCallback((e) => {
    setIsDragging(true);
    const startX = e.clientX - position.x;
    const startY = e.clientY - position.y;
    
    const handleMouseMove = (e) => {
      setPosition({
        x: e.clientX - startX,
        y: e.clientY - startY
      });
    };
    
    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [position]);

  const handleInputChange = useCallback((e) => {
    setReplyText(e.target.value);
    setIsTyping(e.target.value.length > 0);
  }, []);

  const handleSend = useCallback(() => {
    if (!replyText.trim() || sending) return;
    onReply(pending.id, replyText.trim());
    setReplyText('');
    setIsTyping(false);
  }, [replyText, sending, pending, onReply]);

  return (
    <div 
      className="fixed z-50 w-96 rounded-xl shadow-2xl border transition-all duration-300"
      style={{ 
        left: `${position.x}px`,
        top: `${position.y}px`,
        background: 'var(--bg-secondary)',
        borderColor: 'var(--border-subtle)',
        boxShadow: '0 20px 25px rgba(0, 0, 0, 0.15)'
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex items-center gap-3">
          <Avatar name={agentId} size="sm" />
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {agentId}
            </div>
            <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              {status === 'running' ? 'Active' : status === 'blocked' ? 'Blocked' : 'Idle'}
            </div>
          </div>
        </div>
        
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg transition-colors"
          style={{ color: 'var(--text-tertiary)' }}
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="h-80 overflow-y-auto p-4">
        {store.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
              No messages yet
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {store.map(msg => (
              <div key={msg.id} className="flex gap-3">
                <Avatar name={agentId} size="sm" />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      @{agentId}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      {formatRelativeTime(msg.created_at)}
                    </span>
                  </div>
                  {msg.question && (
                    <div className="p-3 rounded-lg"
                      style={{ 
                        background: 'var(--bg-tertiary)', 
                        border: '1px solid var(--border-subtle)' 
                      }}
                    >
                      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        {msg.question}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Reply Bar */}
      <div className="p-4 border-t"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex gap-2">
          <input
            value={replyText}
            onChange={handleInputChange}
            placeholder="Type your reply..."
            disabled={sending}
            className="flex-1 px-3 py-2 rounded-lg text-sm"
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
              opacity: sending ? 0.6 : 1
            }}
          />
          <button
            onClick={handleSend}
            disabled={!replyText.trim() || sending}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200"
            style={{
              background: (!replyText.trim() || sending) ? 'var(--bg-tertiary)' : 'var(--accent-primary)',
              color: (!replyText.trim() || sending) ? 'var(--text-tertiary)' : 'var(--bg-primary)',
              opacity: sending ? 0.8 : 1
            }}
          >
            {sending ? '...' : 'Send'}
          </button>
        </div>
      </div>

      {/* Drag handle */}
      <div
        ref={dragRef}
        onMouseDown={handleMouseDown}
        className="absolute top-0 left-0 right-0 h-6 cursor-move flex items-center justify-center"
        style={{ 
          background: 'var(--accent-primary)',
          cursor: isDragging ? 'grabbing' : 'grab'
        }}
      >
        <div className="w-8 h-0.5 bg-white/30 rounded-full" />
      </div>
    </div>
  );
}

function DateSeparator({ date }) {
  return (
    <div className="flex items-center justify-center my-6">
      <div className="px-3 py-1 rounded-full text-xs font-medium"
        style={{ 
          background: 'var(--bg-tertiary)', 
          color: 'var(--text-tertiary)',
          border: '1px solid var(--border-subtle)'
        }}
      >
        {new Date(date).toLocaleDateString('en-US', { 
          weekday: 'short', 
          month: 'short', 
          day: 'numeric' 
        })}
      </div>
    </div>
  );
}
