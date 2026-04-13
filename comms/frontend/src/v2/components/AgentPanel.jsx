import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Badge, Avatar } from './ui';

const PAGE_SIZE = 10;

/* ─── Fluent UI Agent Panel — Fixed Scroll & Loading ───
   Design:
   • On agent select → load the LATEST messages (most recent first, bottom)
   • Old messages are HIDDEN until the user scrolls up
   • Sentinel sits at the TOP of the scroll container — IntersectionObserver
     loads older messages when it becomes visible
   • Auto-scroll to bottom ONLY when a new message arrives AND user is already
     near the bottom (within 150px)
   • No duplicate messages — WebSocket store is the single source of truth,
     API calls fill in the history
*/

export function AgentPanel({ channels, statuses, messages, activeAgent, setActiveAgent, sending, onReply, busMessages = [] }) {
  const [showChat, setShowChat] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [localReplies, setLocalReplies] = useState({});
  const [showBusMessages, setShowBusMessages] = useState(false);
  const [unreadBusCount, setUnreadBusCount] = useState(0);
  const [seenBusMsgIds, setSeenBusMsgIds] = useState(new Set());

  // Pagination state
  const [apiMessages, setApiMessages] = useState([]);       // messages loaded via API
  const [hasMore, setHasMore] = useState(true);
  const [oldestCursor, setOldestCursor] = useState(null);   // cursor for "before" param
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  // Scroll state
  const [nearBottom, setNearBottom] = useState(true);       // user is near bottom
  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const sentinelRef = useRef(null);
  const storeCountRef = useRef(0);                          // track store message count for new msg detection

  const selectedChannel = channels.find(c => c.agent_id === activeAgent);

  // ─── WebSocket store messages (single source of truth) ───
  const storeMessages = useMemo(() => {
    if (!activeAgent) return [];
    const msgs = messages[activeAgent] ?? [];
    return [...msgs].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }, [activeAgent, messages]);

  // Latest pending message
  const currentPending = useMemo(() => {
    const pending = storeMessages.filter(m => m.status === 'pending');
    if (pending.length === 0) return null;
    return pending.reduce((latest, m) => (new Date(m.created_at) > new Date(latest.created_at) ? m : latest));
  }, [storeMessages]);

  // ─── Merge API + store messages (dedup by id) ───
  // Store messages take precedence; API messages fill gaps for history.
  const allMessages = useMemo(() => {
    const map = new Map();
    // Add API messages first
    for (const m of apiMessages) map.set(m.id, m);
    // Overlay store messages (they are more up-to-date)
    for (const m of storeMessages) map.set(m.id, m);
    return [...map.values()].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }, [apiMessages, storeMessages]);

  // ─── Agent-to-agent messages ───
  const agentBusMessages = useMemo(() => {
    if (!activeAgent) return [];
    return busMessages
      .filter(m => m.from_agent === activeAgent || m.to_agent === activeAgent)
      .sort((a, b) => new Date(b.time) - new Date(a.time));
  }, [activeAgent, busMessages]);

  useEffect(() => {
    if (!activeAgent) return;
    const ids = agentBusMessages.map(m => m.id);
    const newCount = ids.filter(id => !seenBusMsgIds.has(id)).length;
    setUnreadBusCount(newCount);
  }, [agentBusMessages.length, activeAgent, seenBusMsgIds]);

  const markBusMessagesSeen = useCallback(() => {
    const s = new Set(seenBusMsgIds);
    for (const m of agentBusMessages) s.add(m.id);
    setSeenBusMsgIds(s);
    setUnreadBusCount(0);
  }, [agentBusMessages, seenBusMsgIds]);

  const handleBusToggle = useCallback(() => {
    setShowBusMessages(prev => { const n = !prev; if (n) markBusMessagesSeen(); return n; });
  }, [markBusMessagesSeen]);

  // ─── Load latest messages when agent changes ───
  // This loads the MOST RECENT page, not the oldest.
  const loadLatest = useCallback(async () => {
    if (!activeAgent) return;
    try {
      // /api/messages/{agent}/older without "before" = most recent N
      const res = await fetch(`/api/messages/${activeAgent}/older?limit=${PAGE_SIZE}`);
      const data = await res.json(); // DESC order (newest first)
      if (data.length === 0) {
        setApiMessages([]);
        setHasMore(false);
        return;
      }
      const reversed = [...data].reverse(); // now chronological
      setApiMessages(reversed);
      // Cursor = earliest message timestamp for next page
      const earliest = reversed.reduce((min, m) => new Date(m.created_at) < new Date(min.created_at) ? m : min);
      setOldestCursor(earliest.created_at);
      setHasMore(data.length >= PAGE_SIZE);
    } catch (err) {
      console.error('Failed to load latest messages:', err);
    } finally {
      setInitialLoadDone(true);
    }
  }, [activeAgent]);

  // ─── Load older messages (scroll up) ───
  const loadOlder = useCallback(async () => {
    if (loadingOlder || !hasMore || !activeAgent || !oldestCursor) return;
    setLoadingOlder(true);
    try {
      const params = new URLSearchParams({ limit: PAGE_SIZE, before: oldestCursor });
      const res = await fetch(`/api/messages/${activeAgent}/older?${params}`);
      const older = await res.json(); // DESC order
      if (older.length === 0) {
        setHasMore(false);
        return;
      }
      const reversed = [...older].reverse(); // chronological
      setApiMessages(prev => [...reversed, ...prev]);
      const earliest = reversed.reduce((min, m) => new Date(m.created_at) < new Date(min.created_at) ? m : min);
      setOldestCursor(earliest.created_at);
      setHasMore(older.length >= PAGE_SIZE);
    } catch (err) {
      console.error('Failed to load older messages:', err);
    } finally {
      setLoadingOlder(false);
    }
  }, [loadingOlder, hasMore, activeAgent, oldestCursor]);

  // Reset everything when agent changes
  useEffect(() => {
    setApiMessages([]);
    setHasMore(true);
    setOldestCursor(null);
    setNearBottom(true);
    setInitialLoadDone(false);
    storeCountRef.current = 0;
    const s = new Set(seenBusMsgIds);
    for (const m of agentBusMessages) s.add(m.id);
    setSeenBusMsgIds(s);
    setUnreadBusCount(0);
    setReplyText('');
    setLocalReplies({});
  }, [activeAgent]);

  // Trigger initial load
  useEffect(() => {
    if (activeAgent && !initialLoadDone) loadLatest();
  }, [activeAgent, initialLoadDone, loadLatest]);

  // ─── Auto-scroll when new messages arrive ───
  useEffect(() => {
    const count = storeMessages.length;
    const isNew = count > storeCountRef.current;
    storeCountRef.current = count;
    if (isNew && nearBottom) {
      requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }));
    }
  }, [storeMessages.length, nearBottom]);

  // ─── Scroll handler ───
  const handleScroll = useCallback(e => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    // "Near bottom" = within 150px
    setNearBottom(distanceFromBottom < 150);
  }, []);

  // ─── IntersectionObserver on sentinel ───
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !initialLoadDone) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore) {
          loadOlder();
        }
      },
      { root: containerRef.current, rootMargin: '100px 0px 0px 0px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadOlder, hasMore, initialLoadDone]);

  // ─── Actions ───
  const handleAgentClick = agentId => {
    setActiveAgent(agentId);
    setShowChat(true);
  };

  const handleBack = () => { setShowChat(false); setReplyText(''); setLocalReplies({}); };

  const handleSend = async () => {
    if (!currentPending || !replyText.trim()) return;
    const msgId = currentPending.id;
    const text = replyText;
    setLocalReplies(prev => ({ ...prev, [msgId]: text }));
    setReplyText('');
    try { await onReply(msgId, text); }
    catch (err) {
      console.error('Send failed:', err);
      setLocalReplies(prev => { const n = { ...prev }; delete n[msgId]; return n; });
    }
  };

  const handleSuggestionClick = async (suggestion, msgId) => {
    if (!msgId || sending) return;
    setLocalReplies(prev => ({ ...prev, [msgId]: suggestion }));
    try { await onReply(msgId, suggestion); }
    catch (err) {
      console.error('Send failed:', err);
      setLocalReplies(prev => { const n = { ...prev }; delete n[msgId]; return n; });
    }
  };

  const handleKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const busTypeBadge = type => {
    const map = {
      agent_query:     { label: 'query',    bg: 'bg-fluent-warningBg',      text: 'text-fluent-warning' },
      agent_reply:     { label: 'reply',    bg: 'bg-fluent-success/10',    text: 'text-fluent-success' },
      agent_delegate:  { label: 'delegate', bg: 'bg-fluent-accentSubtle',  text: 'text-fluent-accent' },
      agent_context:   { label: 'context',  bg: 'bg-fluent-infoSubtle',    text: 'text-fluent-info' },
      agent_broadcast: { label: 'broadcast',bg: 'bg-fluent-infoSubtle',    text: 'text-fluent-info' },
    };
    return map[type] || { label: type.replace('agent_', ''), bg: 'bg-fluent-card', text: 'text-fluent-textSec' };
  };

  // ─── Render ───
  return (
    <div className="h-full flex flex-col bg-fluent-surface">

      {/* ─── Header ─── */}
      <div className="px-3 py-2.5 border-b border-fluent-borderSubtle flex items-center justify-between flex-shrink-0">
        {!showChat ? (
          <>
            <h2 className="text-sm font-semibold text-fluent-text">Agents</h2>
            <div className="flex items-center gap-2">
              {currentPending && (
                <Badge variant="warning" className="animate-pulse text-[10px]">Needs input</Badge>
              )}
              <span className="text-xs text-fluent-textTert">{channels.length}</span>
            </div>
          </>
        ) : (
          <>
            <button onClick={handleBack}
              className="flex items-center gap-1.5 text-sm text-fluent-textSec hover:text-fluent-text px-2 py-1 rounded-fluent-md hover:bg-fluent-card transition-colors mr-1">
              <ChevronLeftIcon /><span>Back</span>
            </button>
            {selectedChannel && (
              <>
                <Avatar name={activeAgent} size="sm" />
                <div className="flex-1 min-w-0 ml-2">
                  <p className="text-sm font-medium text-fluent-text truncate">{selectedChannel.agent_label || activeAgent}</p>
                  <p className="text-[11px] text-fluent-textTert capitalize">{statuses[activeAgent] || 'idle'}</p>
                </div>
                <button onClick={handleBusToggle}
                  className={`relative p-2 rounded-fluent-md transition-all duration-150 ${
                    showBusMessages ? 'bg-fluent-accentSubtle text-fluent-accent' : 'text-fluent-textTert hover:text-fluent-textSec hover:bg-fluent-card'
                  }`}
                  title="Agent collaboration">
                  <TeamIcon />
                  {unreadBusCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 bg-fluent-accent text-white text-[9px] font-bold rounded-full flex items-center justify-center px-1 animate-scale-in">
                      {unreadBusCount > 9 ? '9+' : unreadBusCount}
                    </span>
                  )}
                </button>
              </>
            )}
          </>
        )}
      </div>

      {/* ─── Agent List ─── */}
      {!showChat && (
        <div className="flex-1 overflow-y-auto">
          {channels.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-fluent-textTert p-4">
              <div className="w-14 h-14 mb-4 rounded-fluent-xl bg-fluent-card flex items-center justify-center">
                <TeamIcon className="w-7 h-7 opacity-40" />
              </div>
              <p className="text-sm">No agents connected</p>
            </div>
          ) : (
            <div className="py-1">
              {channels.map(ch => {
                const status = statuses[ch.agent_id] || 'idle';
                const agentMsg = messages[ch.agent_id] || [];
                const hasPend = agentMsg.some(m => m.status === 'pending');
                const pendCnt = agentMsg.filter(m => m.status === 'pending').length;
                const last = [...agentMsg].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
                const unseen = busMessages
                  .filter(m => (m.from_agent === ch.agent_id || m.to_agent === ch.agent_id) && !seenBusMsgIds.has(m.id));

                return (
                  <button key={ch.agent_id} onClick={() => handleAgentClick(ch.agent_id)}
                    className={`w-full flex items-center gap-3 px-3 py-3 text-left transition-all duration-150 animate-slide-right ${
                      activeAgent === ch.agent_id
                        ? 'bg-fluent-accentSubtle border-l-[3px] border-fluent-accent'
                        : 'hover:bg-fluent-card border-l-[3px] border-transparent'
                    }`}>
                    <div className="relative flex-shrink-0">
                      <Avatar name={ch.agent_id} size="md" />
                      <StatusDot status={status} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-fluent-text truncate">{ch.agent_label || ch.agent_id}</p>
                        <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
                          {unseen.length > 0 && (
                            <span className="px-1.5 py-0.5 rounded-fluent-sm bg-fluent-accentSubtle text-fluent-accent text-[10px] font-semibold flex items-center gap-0.5">
                              <ChatBubbleIcon className="w-2.5 h-2.5" />{unseen.length}
                            </span>
                          )}
                          {hasPend && (
                            <span className="flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-fluent-warning animate-pulse" />
                              {pendCnt > 1 && <span className="text-[10px] text-fluent-warning font-medium">{pendCnt}</span>}
                            </span>
                          )}
                        </div>
                      </div>
                      <p className="text-[11px] text-fluent-textTert capitalize mt-0.5">{status}</p>
                      {last && (
                        <p className="text-[11px] text-fluent-textTert truncate mt-0.5 opacity-70">
                          {last.question?.slice(0, 50) || last.reply?.slice(0, 50) || 'No messages'}
                        </p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─── Chat View ─── */}
      {showChat && activeAgent && (
        <>
          <div ref={containerRef} onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-3 space-y-3">

            {/* Sentinel — always at the very top, triggers loading older messages */}
            {hasMore && initialLoadDone && (
              <div ref={sentinelRef} className="h-1" />
            )}

            {/* Loading indicator (shown when fetching older) */}
            {loadingOlder && (
              <div className="flex items-center justify-center py-2 animate-fade-in">
                <div className="w-4 h-4 border-2 border-fluent-accent border-t-transparent rounded-full animate-spin" />
                <span className="ml-2 text-xs text-fluent-textTert">Loading older…</span>
              </div>
            )}

            {/* Agent-to-agent collaboration */}
            {showBusMessages && agentBusMessages.length > 0 && (
              <div className="mb-2 animate-fade-in">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[11px] font-semibold text-fluent-textTert uppercase tracking-wider">Collaboration</h3>
                    {unreadBusCount > 0 && <Badge variant="warning" className="text-[10px] animate-pulse">{unreadBusCount} new</Badge>}
                  </div>
                  <span className="text-[10px] text-fluent-textTert">{agentBusMessages.length}</span>
                </div>
                <div className="space-y-1">
                  {agentBusMessages.slice(0, 20).map(msg => {
                    const cfg = busTypeBadge(msg.type);
                    const unread = !seenBusMsgIds.has(msg.id);
                    return (
                      <div key={msg.id}
                        className={`rounded-fluent-lg border p-2 text-[11px] transition-colors duration-150 ${
                          unread ? 'border-fluent-accentBorder bg-fluent-accentSubtle' : 'border-fluent-borderSubtle bg-fluent-surfaceAlt/40'
                        }`}>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className={`px-1.5 py-0.5 rounded-fluent-sm font-mono text-[10px] ${cfg.bg} ${cfg.text}`}>{cfg.label}</span>
                          <Avatar name={msg.from_agent} size="xs" />
                          <span className="text-fluent-textSec">@{msg.from_agent}</span>
                          {msg.to_agent && (<>
                            <span className="text-fluent-textTert">→</span>
                            <Avatar name={msg.to_agent} size="xs" />
                            <span className="text-fluent-textSec">@{msg.to_agent}</span>
                          </>)}
                          <span className="text-fluent-textTert ml-auto">{formatTime(msg.time)}</span>
                        </div>
                        <p className="text-fluent-textSec">{msg.text}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ─── Messages ─── */}
            {allMessages.length === 0 && !initialLoadDone && (
              <div className="flex items-center justify-center py-8">
                <div className="w-5 h-5 border-2 border-fluent-accent border-t-transparent rounded-full animate-spin" />
              </div>
            )}

            {allMessages.length === 0 && initialLoadDone && (
              <div className="flex flex-col items-center justify-center h-full text-fluent-textTert">
                <div className="w-14 h-14 mb-4 rounded-fluent-xl bg-fluent-card flex items-center justify-center">
                  <ChatBubbleIcon className="w-7 h-7 opacity-40" />
                </div>
                <p className="text-sm">{currentPending ? 'New message' : 'No messages yet'}</p>
              </div>
            )}

            {allMessages.map(msg => {
              const isCurrentPending = msg.id === currentPending?.id;
              const userReply = localReplies[msg.id] || msg.reply;

              return (
                <div key={msg.id} className="space-y-2 animate-slide-up">
                  {/* Agent message bubble */}
                  <div className={`rounded-fluent-xl border p-3 transition-colors duration-150 ${
                    isCurrentPending && !userReply
                      ? 'border-fluent-warningBorder bg-fluent-warningBg'
                      : 'border-fluent-borderSubtle bg-fluent-surfaceAlt/60 hover:bg-fluent-surfaceAlt/80'
                  }`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <Avatar name={msg.agent_id} size="sm" />
                        <span className="text-xs font-medium text-fluent-textSec">@{msg.agent_id}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isCurrentPending && !userReply && (
                          <span className="flex items-center gap-1 text-[11px] text-fluent-warning">
                            <span className="w-1.5 h-1.5 rounded-full bg-fluent-warning animate-pulse" />
                            Awaiting
                          </span>
                        )}
                        <span className="text-[11px] text-fluent-textTert">{formatTime(msg.created_at)}</span>
                      </div>
                    </div>

                    <p className="text-sm text-fluent-text leading-relaxed whitespace-pre-wrap">{msg.question}</p>

                    {msg.suggestions?.length > 0 && isCurrentPending && !userReply && (
                      <div className="border-t border-fluent-borderSubtle pt-2 mt-2">
                        <p className="text-[11px] text-fluent-textTert mb-1.5">Quick replies:</p>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.suggestions.map((s, i) => (
                            <button key={i}
                              onClick={() => handleSuggestionClick(s, msg.id)}
                              disabled={sending}
                              className="text-xs px-2.5 py-1 rounded-fluent-lg bg-fluent-surfaceAlt border border-fluent-borderSubtle text-fluent-textSec
                                         hover:bg-fluent-accentSubtle hover:border-fluent-accentBorder hover:text-fluent-accent
                                         transition-all duration-150 disabled:opacity-40 active:scale-[0.97]">
                              {s.length > 40 ? s.slice(0, 40) + '…' : s}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* User reply bubble */}
                  {userReply && (
                    <div className="rounded-fluent-xl border border-fluent-success/30 bg-fluent-success/5 p-3 ml-6 animate-slide-up">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <div className="w-5 h-5 rounded-full bg-fluent-success/15 flex items-center justify-center">
                          <UserIcon />
                        </div>
                        <span className="text-xs font-medium text-fluent-success">You</span>
                        <span className="text-[11px] text-fluent-textTert ml-auto">{formatTime(msg.replied_at || msg.created_at)}</span>
                      </div>
                      <p className="text-sm text-fluent-text leading-relaxed whitespace-pre-wrap">{userReply}</p>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Bottom sentinel for auto-scroll */}
            <div ref={bottomRef} className="h-0" />
          </div>

          {/* ─── Reply Input ─── */}
          <div className="border-t border-fluent-borderSubtle p-3 space-y-2 bg-fluent-surfaceAlt flex-shrink-0">
            <textarea
              value={replyText}
              onChange={e => setReplyText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={currentPending ? 'Type your reply…' : 'No pending requests'}
              disabled={!currentPending || sending}
              rows={2}
              className="w-full bg-fluent-surface border border-fluent-border rounded-fluent-lg px-3 py-2.5 text-sm text-fluent-text
                         placeholder:text-fluent-textTert focus:outline-none focus:border-fluent-accentBorder focus:ring-1 focus:ring-fluent-accent/20
                         resize-none disabled:opacity-40 transition-all duration-150 font-sans"
            />
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-fluent-textTert">
                {currentPending ? `Replying to @${activeAgent}` : 'Idle'}
              </span>
              <button onClick={handleSend}
                disabled={!currentPending || !replyText.trim() || sending}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-fluent-lg bg-fluent-accent
                           hover:bg-fluent-accentHover disabled:opacity-40 disabled:cursor-not-allowed
                           text-white text-sm font-medium transition-all duration-150 active:scale-[0.97]
                           shadow-fluent-card">
                {sending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/60 border-t-transparent rounded-full animate-spin" />
                    Sending
                  </>
                ) : (
                  <><SendIcon />Send</>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ═══ Small components ═══ */

function StatusDot({ status }) {
  const color = status === 'running' ? 'bg-fluent-success' : status === 'idle' ? 'bg-fluent-textTert' : 'bg-fluent-warning';
  const anim = status === 'running' ? 'animate-pulse' : '';
  return <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-fluent-surface ${color} ${anim}`} />;
}

function ChevronLeftIcon({ className }) {
  return <svg className={className || 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>;
}
function TeamIcon({ className }) {
  return <svg className={className || 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>;
}
function ChatBubbleIcon({ className }) {
  return <svg className={className || 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>;
}
function SendIcon() {
  return <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>;
}
function UserIcon() {
  return <svg className="w-3 h-3 text-fluent-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>;
}

function formatTime(ts) {
  if (!ts) return '';
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 5) return 'Just now';
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}
