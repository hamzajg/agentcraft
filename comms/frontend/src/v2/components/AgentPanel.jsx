import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Badge, Avatar } from './ui';

const PAGE = 15;

/* ─────────────────────────────────────────────────────────
   AgentPanel — rebuilt from scratch
   Rules:
   1. Show ONLY the latest conversation messages (WebSocket store)
   2. Auto-scroll to bottom on new messages
   3. Load older history ONLY when user scrolls to the very top
   4. Sentinel at top → IntersectionObserver → loadOlder()
   5. No duplicate messages — Map dedup by id
   ───────────────────────────────────────────────────────── */

export function AgentPanel({ channels, statuses, messages, activeAgent, setActiveAgent, sending, onReply, busMessages = [] }) {
  const [showChat, setShowChat] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [localReplies, setLocalReplies] = useState({});
  const [showBus, setShowBus] = useState(false);
  const [unreadBus, setUnreadBus] = useState(0);
  const [seenBusIds, setSeenBusIds] = useState(new Set());

  // Older-message pagination (loaded from API on scroll-up)
  const [history, setHistory] = useState([]);       // older messages prepended here
  const [hasMore, setHasMore] = useState(true);
  const [cursor, setCursor] = useState(null);       // before= timestamp
  const [loading, setLoading] = useState(false);

  // Scroll tracking
  const [atBottom, setAtBottom] = useState(true);
  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const topRef = useRef(null);
  const storeLenRef = useRef(0);

  const selected = channels.find(c => c.agent_id === activeAgent);

  // ── WebSocket store messages (chronological) ──
  const store = useMemo(() => {
    if (!activeAgent) return [];
    return (messages[activeAgent] ?? [])
      .slice()
      .sort((a, b) => d(a) - d(b));
  }, [activeAgent, messages]);

  // Latest pending message
  const pending = useMemo(() => {
    const p = store.filter(m => m.status === 'pending');
    return p.length ? p.reduce((a, b) => d(b) > d(a) ? b : a) : null;
  }, [store]);

  // ── Merge history + store (dedup by id) ──
  const all = useMemo(() => {
    const m = new Map();
    for (const x of history) m.set(x.id, x);
    for (const x of store)   m.set(x.id, x);   // store wins (more up-to-date)
    return [...m.values()].sort((a, b) => d(a) - d(b));
  }, [history, store]);

  // ── Agent-to-agent bus messages ──
  const busMsgs = useMemo(() => {
    if (!activeAgent) return [];
    return busMessages
      .filter(m => m.from_agent === activeAgent || m.to_agent === activeAgent)
      .sort((a, b) => d(b) - d(a));
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

  // ── Load older messages (cursor pagination) ──
  const loadOlder = useCallback(async () => {
    if (loading || !hasMore || !activeAgent) return;
    setLoading(true);
    try {
      const url = new URL(`/api/messages/${activeAgent}/older`, location.origin);
      url.searchParams.set('limit', String(PAGE));
      if (cursor) url.searchParams.set('before', cursor);

      const res = await fetch(url);
      const data = await res.json();          // DESC (newest first)
      if (!data.length || data.length < PAGE) setHasMore(false);
      if (data.length) {
        const chrono = [...data].reverse();   // chronological
        setHistory(prev => [...chrono, ...prev]);
        setCursor(d(chrono[0]));              // earliest loaded → next cursor
      }
    } catch (e) {
      console.error('loadOlder', e);
    } finally {
      setLoading(false);
    }
  }, [loading, hasMore, activeAgent, cursor]);

  // ── Reset everything on agent switch ──
  useEffect(() => {
    setHistory([]);
    setHasMore(true);
    setCursor(null);
    setAtBottom(true);
    storeLenRef.current = 0;
    setReplyText('');
    setLocalReplies({});
    const s = new Set(seenBusIds);
    busMsgs.forEach(m => s.add(m.id));
    setSeenBusIds(s);
    setUnreadBus(0);
  }, [activeAgent]);

  // ── Auto-scroll when new WebSocket messages arrive ──
  useEffect(() => {
    const len = store.length;
    if (len > storeLenRef.current && atBottom) {
      requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }));
    }
    storeLenRef.current = len;
  }, [store.length, atBottom]);

  // ── Scroll handler: track "at bottom" ──
  const onScroll = useCallback(e => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const gap = scrollHeight - scrollTop - clientHeight;
    setAtBottom(gap < 120);
  }, []);

  // ── IntersectionObserver on top sentinel ──
  useEffect(() => {
    const el = topRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting && hasMore) loadOlder(); },
      { root: containerRef.current, rootMargin: '80px 0px 0px 0px' },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadOlder, hasMore]);

  // ── Actions ──
  const pickAgent = id => { setActiveAgent(id); setShowChat(true); };
  const goBack = () => { setShowChat(false); setReplyText(''); setLocalReplies({}); };

  const sendReply = async () => {
    if (!pending || !replyText.trim()) return;
    const id = pending.id;
    const txt = replyText;
    setLocalReplies(p => ({ ...p, [id]: txt }));
    setReplyText('');
    try { await onReply(id, txt); }
    catch (e) {
      console.error(e);
      setLocalReplies(p => { const n = { ...p }; delete n[id]; return n; });
    }
  };

  const tapSuggestion = async (s, id) => {
    if (!id || sending) return;
    setLocalReplies(p => ({ ...p, [id]: s }));
    try { await onReply(id, s); }
    catch (e) {
      console.error(e);
      setLocalReplies(p => { const n = { ...p }; delete n[id]; return n; });
    }
  };

  const onKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply(); } };

  const busBadge = type => {
    const m = {
      agent_query:     { l: 'query',    bg: 'bg-amber/10',       t: 'text-amber' },
      agent_reply:     { l: 'reply',    bg: 'bg-teal/10',        t: 'text-teal' },
      agent_delegate:  { l: 'delegate', bg: 'bg-violet/10',      t: 'text-violet' },
      agent_context:   { l: 'context',  bg: 'bg-blue-500/10',    t: 'text-blue-400' },
      agent_broadcast: { l: 'broadcast',bg: 'bg-cyan-500/10',    t: 'text-cyan-400' },
    };
    return m[type] || { l: type.replace('agent_', ''), bg: 'bg-slate-700', t: 'text-slate-400' };
  };

  // ═══════════════════════════════════════════════════════
  //  RENDER
  // ═══════════════════════════════════════════════════════
  return (
    <div className="h-full flex flex-col bg-[#131313]">

      {/* ─── Header ─── */}
      <HeaderRow
        showChat={showChat}
        channels={channels}
        pending={pending}
        selected={selected}
        activeAgent={activeAgent}
        status={statuses[activeAgent]}
        unreadBus={unreadBus}
        showBus={showBus}
        onBack={goBack}
        onBusToggle={() => setShowBus(p => { const n = !p; if (n) markBus(); return n; })}
      />

      {/* ─── Agent List ─── */}
      {!showChat && (
        <AgentList
          channels={channels}
          statuses={statuses}
          messages={messages}
          activeAgent={activeAgent}
          busMessages={busMessages}
          seenBusIds={seenBusIds}
          onSelect={pickAgent}
        />
      )}

      {/* ─── Chat View ─── */}
      {showChat && activeAgent && (
        <>
          {/* Scroll container */}
          <div ref={containerRef} onScroll={onScroll}
            className="flex-1 overflow-y-auto px-3 py-3 space-y-3">

            {/* Top sentinel — invisible trigger for loading older */}
            <div ref={topRef} className="h-0" />

            {/* Loading spinner */}
            {loading && (
              <div className="flex items-center justify-center py-2">
                <Spinner size={16} />
                <span className="ml-2 text-[11px] text-zinc-500">Loading history…</span>
              </div>
            )}

            {/* Bus messages panel */}
            {showBus && busMsgs.length > 0 && (
              <BusPanel msgs={busMsgs} badge={busBadge} seen={seenBusIds} />
            )}

            {/* Empty state */}
            {!all.length && (
              <div className="flex flex-col items-center justify-center py-16 text-zinc-500">
                <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center mb-3">
                  <ChatIcon className="w-6 h-6 opacity-40" />
                </div>
                <p className="text-sm">{pending ? 'New message' : 'No messages yet'}</p>
              </div>
            )}

            {/* Messages */}
            {all.map(msg => {
              const isPending = msg.id === pending?.id;
              const reply = localReplies[msg.id] || msg.reply;
              return (
                <MsgBubble
                  key={msg.id}
                  msg={msg}
                  isPending={isPending}
                  reply={reply}
                  suggestions={msg.suggestions}
                  sending={sending}
                  onSuggest={s => tapSuggestion(s, msg.id)}
                />
              );
            })}

            {/* Bottom anchor for auto-scroll */}
            <div ref={bottomRef} className="h-0" />
          </div>

          {/* ─── Reply bar ─── */}
          <ReplyBar
            replyText={replyText}
            setReplyText={setReplyText}
            onKeyDown={onKey}
            hasPending={!!pending}
            agentId={activeAgent}
            sending={sending}
            onSend={sendReply}
          />
        </>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Sub-components
   ══════════════════════════════════════════════════════════ */

function HeaderRow({ showChat, channels, pending, selected, activeAgent, status, unreadBus, showBus, onBack, onBusToggle }) {
  return (
    <div className="px-3 py-2.5 border-b border-zinc-800 flex items-center justify-between flex-shrink-0">
      {!showChat ? (
        <>
          <h2 className="text-sm font-semibold text-zinc-100">Agents</h2>
          <div className="flex items-center gap-2">
            {pending && <Badge variant="warning" className="animate-pulse text-[10px]">Needs input</Badge>}
            <span className="text-xs text-zinc-500">{channels.length}</span>
          </div>
        </>
      ) : (
        <>
          <button onClick={onBack}
            className="flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded-md hover:bg-zinc-800 transition mr-1">
            <ChevronLeft />Back
          </button>
          {selected && (
            <>
              <Avatar name={activeAgent} size="sm" />
              <div className="flex-1 min-w-0 ml-2">
                <p className="text-sm font-medium text-zinc-100 truncate">{selected.agent_label || activeAgent}</p>
                <p className="text-[11px] text-zinc-500 capitalize">{status || 'idle'}</p>
              </div>
              <button onClick={onBusToggle}
                className={`relative p-1.5 rounded-md transition ${showBus ? 'bg-violet/20 text-violet' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'}`}>
                <TeamIcon />
                {unreadBus > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 bg-violet text-white text-[9px] font-bold rounded-full flex items-center justify-center px-1">
                    {unreadBus > 9 ? '9+' : unreadBus}
                  </span>
                )}
              </button>
            </>
          )}
        </>
      )}
    </div>
  );
}

function AgentList({ channels, statuses, messages, activeAgent, busMessages, seenBusIds, onSelect }) {
  if (!channels.length) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-zinc-500">
        <TeamIcon className="w-10 h-10 opacity-30 mb-3" />
        <p className="text-sm">No agents connected</p>
      </div>
    );
  }
  return (
    <div className="flex-1 overflow-y-auto py-1">
      {channels.map(ch => {
        const st = statuses[ch.agent_id] || 'idle';
        const m = messages[ch.agent_id] || [];
        const pend = m.filter(x => x.status === 'pending');
        const last = m.length ? m.slice().sort((a, b) => d(b) - d(a))[0] : null;
        const unseen = busMessages.filter(x =>
          (x.from_agent === ch.agent_id || x.to_agent === ch.agent_id) && !seenBusIds.has(x.id));

        return (
          <button key={ch.agent_id} onClick={() => onSelect(ch.agent_id)}
            className={`w-full flex items-center gap-3 px-3 py-3 text-left transition ${
              activeAgent === ch.agent_id ? 'bg-indigo-500/10 border-l-2 border-indigo-500' : 'hover:bg-zinc-800/50 border-l-2 border-transparent'
            }`}>
            <div className="relative">
              <Avatar name={ch.agent_id} size="md" />
              <Dot status={st} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-zinc-100 truncate">{ch.agent_label || ch.agent_id}</p>
                <div className="flex items-center gap-1.5 ml-2">
                  {unseen.length > 0 && (
                    <span className="px-1 py-px rounded bg-violet/15 text-violet text-[10px] font-semibold flex items-center gap-0.5">
                      <ChatIcon className="w-2.5 h-2.5" />{unseen.length}
                    </span>
                  )}
                  {pend.length > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber animate-pulse" />
                      {pend.length > 1 && <span className="text-[10px] text-amber">{pend.length}</span>}
                    </span>
                  )}
                </div>
              </div>
              <p className="text-[11px] text-zinc-500 capitalize mt-0.5">{st}</p>
              {last && (
                <p className="text-[11px] text-zinc-600 truncate mt-0.5">
                  {last.question?.slice(0, 50) || last.reply?.slice(0, 50) || '—'}
                </p>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function MsgBubble({ msg, isPending, reply, suggestions, sending, onSuggest }) {
  return (
    <div className="space-y-2 animate-slide-up">
      {/* Agent bubble */}
      <div className={`rounded-xl border p-3 transition ${
        isPending && !reply ? 'border-amber/30 bg-amber/5' : 'border-zinc-800 bg-zinc-800/40 hover:bg-zinc-800/60'
      }`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Avatar name={msg.agent_id} size="sm" />
            <span className="text-xs font-medium text-zinc-400">@{msg.agent_id}</span>
          </div>
          <div className="flex items-center gap-2">
            {isPending && !reply && (
              <span className="flex items-center gap-1 text-[11px] text-amber">
                <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" /> Awaiting
              </span>
            )}
            <span className="text-[11px] text-zinc-600">{ago(msg.created_at)}</span>
          </div>
        </div>

        {msg.question && <p className="text-sm text-zinc-100 whitespace-pre-wrap leading-relaxed">{msg.question}</p>}

        {msg.file && (
          <div className="mt-2 flex items-center gap-2 text-xs bg-zinc-900 rounded-lg border border-zinc-700 px-2.5 py-1.5 w-fit">
            <FileIcon className="w-3.5 h-3.5 text-zinc-500" />
            <code className="text-zinc-400">{msg.file}</code>
          </div>
        )}

        {suggestions?.length > 0 && isPending && !reply && (
          <div className="border-t border-zinc-700/50 pt-2 mt-2">
            <p className="text-[11px] text-zinc-500 mb-1.5">Quick replies:</p>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((s, i) => (
                <button key={i} onClick={() => onSuggest(s)} disabled={sending}
                  className="text-xs px-2.5 py-1 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-300
                             hover:bg-indigo-500/15 hover:border-indigo-500/30 hover:text-indigo-300
                             transition disabled:opacity-40 active:scale-[0.97]">
                  {s.length > 40 ? s.slice(0, 40) + '…' : s}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* User reply */}
      {reply && (
        <div className="rounded-xl border border-teal/25 bg-teal/5 p-3 ml-6">
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-5 h-5 rounded-full bg-teal/15 flex items-center justify-center"><UserIcon /></div>
            <span className="text-xs font-medium text-teal">You</span>
            <span className="text-[11px] text-zinc-600 ml-auto">{ago(msg.replied_at || msg.created_at)}</span>
          </div>
          <p className="text-sm text-zinc-100 whitespace-pre-wrap">{reply}</p>
        </div>
      )}
    </div>
  );
}

function ReplyBar({ replyText, setReplyText, onKeyDown, hasPending, agentId, sending, onSend }) {
  return (
    <div className="border-t border-zinc-800 p-3 space-y-2 bg-zinc-900/60 flex-shrink-0">
      <textarea
        value={replyText} onChange={e => setReplyText(e.target.value)} onKeyDown={onKeyDown}
        placeholder={hasPending ? 'Type your reply…' : 'No pending requests'}
        disabled={!hasPending || sending} rows={2}
        className="w-full bg-[#131313] border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100
                   placeholder:text-zinc-600 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20
                   resize-none disabled:opacity-40 transition font-sans"
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-zinc-600">{hasPending ? `Replying to @${agentId}` : 'Idle'}</span>
        <button onClick={onSend}
          disabled={!hasPending || !replyText.trim() || sending}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600
                     hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed
                     text-white text-sm font-medium transition active:scale-[0.97]">
          {sending ? <><Spinner size={14} />Sending</> : <><SendIcon />Send</>}
        </button>
      </div>
    </div>
  );
}

function BusPanel({ msgs, badge, seen }) {
  return (
    <div className="mb-2">
      <h3 className="text-[11px] font-semibold text-zinc-600 uppercase tracking-wider mb-2">Collaboration</h3>
      <div className="space-y-1">
        {msgs.slice(0, 20).map(m => {
          const b = badge(m.type);
          const u = !seen.has(m.id);
          return (
            <div key={m.id}
              className={`rounded-lg border p-2 text-[11px] transition ${u ? 'border-violet/30 bg-violet/5' : 'border-zinc-800 bg-zinc-800/30'}`}>
              <div className="flex items-center gap-1 mb-0.5">
                <span className={`px-1.5 py-px rounded font-mono text-[10px] ${b.bg} ${b.t}`}>{b.l}</span>
                <span className="text-zinc-400">@{m.from_agent}</span>
                {m.to_agent && <><span className="text-zinc-600">→</span><span className="text-zinc-400">@{m.to_agent}</span></>}
                <span className="text-zinc-600 ml-auto">{ago(m.time)}</span>
              </div>
              <p className="text-zinc-400">{m.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══ Tiny helpers ═══ */

function d(x) { return new Date(x.created_at || x.time); }
function ago(ts) {
  if (!ts) return '';
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 5) return 'now';
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${~~(s / 60)}m`;
  return `${~~(s / 3600)}h`;
}

/* ═══ Icons ═══ */
function Spinner({ size }) {
  return <div className={`border-2 border-white/50 border-t-transparent rounded-full animate-spin`} style={{ width: size, height: size }} />;
}
function ChevronLeft() { return <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>; }
function TeamIcon({ className }) { return <svg className={className || 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>; }
function ChatIcon({ className }) { return <svg className={className || 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>; }
function SendIcon() { return <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>; }
function FileIcon({ className }) { return <svg className={className || 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>; }
function UserIcon() { return <svg className="w-3 h-3 text-teal" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>; }

function Dot({ status }) {
  const c = status === 'running' ? 'bg-emerald-500' : status === 'idle' ? 'bg-zinc-500' : 'bg-amber';
  const a = status === 'running' ? 'animate-pulse' : '';
  return <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#131313] ${c} ${a}`} />;
}
