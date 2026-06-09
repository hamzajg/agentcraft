# AgentCraft → Hermes: Full Architecture & Experience Refactor

## Overview

**Hermes** (the Greek messenger god — swift, omniscient, divine intermediary between worlds) is the perfect metaphor for an AI agentic software development platform: a fleet of specialist agents communicating at divine speed, coordinated by a central intelligence, observable by a human overseer.

This plan refactors AgentCraft end-to-end to deliver the **Hermes experience** — a premium, immersive AI agent command-center identity replacing the current generic "AgentCraft" brand. The refactor spans three layers:

1. **Frontend** — new design identity, component architecture, and Hermes-branded workspace
2. **Backend agents** — a new `HermesAgent` coordinator, agent persona upgrades, and new API endpoints
3. **Infrastructure** — clean state management, a proper hooks layer, and production-ready WebSocket integration

---

## User Review Required

> [!IMPORTANT]
> **Hermes Color Palette Decision**: The current design uses `#00d4ff` (electric cyan) as the accent. Hermes mythology suggests **gold/amber** (#FFB830) as the primary accent with electric blue as secondary, for a "divine messenger" feel. Alternatively, we can keep cyan but layer in gold highlights.  
> *Please confirm which direction you prefer — or specify a third option.*

> [!IMPORTANT]
> **HermesAgent scope**: Should the new `HermesAgent` be a fully autonomous LLM-backed agent that can hold a real conversation and delegate tasks, or a UI-facade persona layer (smart routing + display only)?

> [!WARNING]
> **Breaking routing change**: This plan replaces the current `/` → LandingPage, `/workspace/*` → GlobalLayout structure with a new `/` → HermesLanding, `/hermes/*` route structure. All existing deep links to `/workspace` will redirect.

> [!WARNING]
> **AgentPanelRedesigned.jsx** (1,150 lines) will be decomposed into ~6 focused components. The file will be deleted and replaced. Any future changes targeting it must be redirected to the new structure.

---

## ✅ Approved Clarifications

| Decision | Answer |
|---|---|
| **Branding** | Build **AgentCraft Hermes Studio** as a fully separate derived product at `/hermes`. Old system at `/workspace` stays 100% untouched. |
| **HermesChat** | Center column shows Hermes chat by default; user can switch to per-agent chat. All new components. |
| **Constellation** | Dedicated tab with `/hermes/agents` route. All new components. |
| **Logo** | Generate a new Hermes-specific logo/icon asset. |

---

## Proposed Changes

---

### 1. Design System — `design-system.css`

Elevate from generic dark-blue to a **Hermes Identity System** with mythology-inspired tokens.

#### [MODIFY] [design-system.css](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/styles/design-system.css)

**Changes:**
- Add Hermes color palette layer: `--hermes-gold: #FFB830`, `--hermes-gold-dim`, `--hermes-gold-glow`
- Add `--bg-void: #07090f` (deeper space background for the landing)
- Add `--gradient-hermes` (diagonal gold-to-cyan gradient for hero elements)
- Add animation keyframes: `hermes-glow`, `constellation-pulse`, `message-fly`
- Add `.hermes-glow` utility — glowing gold border effect for active agent cards
- Add `.constellation-node` — circular pulsing node for the agent network view
- Add `.stream-line` — animated line connecting constellation nodes
- Update font stack: keep Orbitron (display), Inter (body), JetBrains Mono (code) — add **Cinzel** for the Hermes brand wordmark only

---

### 2. Landing Page — Full Hermes Experience Redesign

#### [MODIFY] [LandingPage.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/pages/LandingPage.jsx)

Replace the current minimal card layout with a full immersive hero experience:

- **Hero Section**: Full-viewport animated background — radial constellation particle field (pure CSS/SVG, no canvas), Hermes wordmark in Cinzel font with gold glow, animated winged caduceus icon (SVG)
- **Agent Constellation Preview**: Static mini-constellation showing all 11 agents as glowing nodes with labels and animated connection lines between them. Purely cosmetic/illustrative
- **Feature Pillars** (3 animated cards with scroll-triggered entrance):
  - ⚡ *Instant Delegation* — Hermes routes tasks to specialist agents in milliseconds
  - 🧠 *Shared Intelligence* — All agents share a live RAG knowledge base
  - 👁 *Full Observability* — Watch every agent thought, decision, and file written in real time
- **Enter Hermes CTA**: Large glowing gold button → `/hermes/workspace`
- **Footer**: Hermes mythology quote — *"Swift as thought, precise as fate."*

---

### 3. Global Layout Replacement

#### [MODIFY] [GlobalLayout.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/GlobalLayout.jsx)

Rename conceptually to **HermesShell** and refactor:

**Current problems:**
- Emoji icons (📁📊📡🔍) — unprofessional
- Basic tab buttons with no visual hierarchy
- Route sync is fragile (path split on `/`)

**New structure:**
- Replace emoji tabs with proper SVG icon set from `icons.jsx`
- Add **Hermes TopBar**: left = Hermes wordmark + status dot (online/building/idle), center = global build progress bar (phase indicator), right = notification bell + settings
- Navigation becomes a **vertical icon sidebar** (64px, always visible) with tooltips — more screen space for content
- Tabs: Workspace · Agents · RAG · Monitor · Events · Settings
- Active route uses gold accent indicator, not background fill

#### [NEW] [HermesTopBar.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/layout/HermesTopBar.jsx)

Top bar component extracted from GlobalLayout with:
- Hermes brand wordmark (Cinzel font + gold color)
- Live build phase chip (idle / building phase N / complete)
- Global pending-reply badge count
- Settings gear icon

#### [NEW] [HermesSidebar.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/layout/HermesSidebar.jsx)

Vertical navigation sidebar replacing horizontal tab bar:
- 64px wide, icons only (expandable to 200px on hover)
- SVG icons for each section
- Gold active indicator strip on the left edge of active item
- Agent count + status summary mini-widget at bottom

---

### 4. Workspace Tab — Enhanced 3-Column Layout

#### [MODIFY] [WorkspaceLayout.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/WorkspaceLayout.jsx)

**Current problems:**
- WebSocket handlers are stubs (`console.log('WebSocket message:', data)`)
- Channels, statuses, messages are never populated from real data
- AgentBuildOverlay exists but uses a polling mechanism that's disconnected from the real ES event stream

**New implementation:**
- Remove all stub handlers, wire to real `useAgentData()` hook (see hooks section)
- Replace `useWebSocket` stub with full event handler for: `init`, `clarification`, `reply_confirmed`, `agent_status`, `channels_updated`, `agents_built`
- Left panel (FileExplorer): keep, add breadcrumb path display
- Center panel: keep FileViewer + FluentEmptyState, add **HermesConsole** mode (toggle between file view and Hermes chat center)
- Right panel: Replace `AgentPanelRedesigned` with new decomposed `AgentSidebar`
- Bottom ActivityPanel: Expand to show the event stream with proper event-type icons and filtering
- Remove polling-based AgentBuildOverlay, replace with event-driven notification toast

---

### 5. Agent Panel Decomposition

**The 1,150-line `AgentPanelRedesigned.jsx` is decomposed into:**

#### [DELETE] [AgentPanelRedesigned.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/AgentPanelRedesigned.jsx)

Replaced by the following focused components:

#### [NEW] [AgentSidebar.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/AgentSidebar.jsx)

Container (≤80 lines) — orchestrates the agent panel. Manages view state: `list` | `chat`. Passes data from hooks, renders `AgentList` or `AgentChatView`.

#### [NEW] [AgentList.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/AgentList.jsx)

Agent roster list (≤120 lines):
- Renders `AgentCard` for each channel
- Groups by status: Active · Blocked · Idle (collapsible groups)
- Search/filter input at top
- Hermes-styled cards with gold highlight for blocked agents (pending reply)

#### [NEW] [AgentCard.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/AgentCard.jsx)

Individual agent card (≤80 lines):
- Avatar with animated status ring (pulsing gold for blocked, green for running)
- Agent role name + description
- Message count + unread bus count badges
- `onClick` → opens chat view

#### [NEW] [AgentChatView.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/AgentChatView.jsx)

Full chat thread for a selected agent (≤200 lines):
- Message list with infinite scroll (load older)
- `DateSeparator` between days
- Bus messages toggle
- Back button → AgentList
- Passes message render to `MessageBubble`

#### [NEW] [MessageBubble.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/MessageBubble.jsx)

Individual message render (≤100 lines):
- Agent question bubble (left-aligned, dark card)
- User reply bubble (right-aligned, gold accent)
- `FileAttachment` sub-component
- Quick reply suggestions (collapsible chip list)
- Pending highlight (gold glow border + pulse)

#### [NEW] [ReplyBar.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/ReplyBar.jsx)

Reply input area (≤80 lines):
- Auto-resizing textarea
- Send button (disabled/enabled state)
- `@agent-name` mention support
- Keyboard shortcut hint

#### [NEW] [CollapsedAgentBar.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/agents/CollapsedAgentBar.jsx)

Collapsed avatar strip (≤60 lines) — extracted from current inline code

---

### 6. Hermes Chat Center (New Feature)

#### [NEW] [HermesChat.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/HermesChat.jsx)

A new primary communication panel — the **Hermes Console** — where the human talks directly to "Hermes" who routes requests to agents:

- Centered chat interface (like Claude/ChatGPT but dark+gold themed)
- Input: "Tell Hermes what to build..." with gold glowing border on focus
- Message history: Hermes replies shown with winged avatar
- When Hermes delegates to a specialist agent, shows a compact "routing card": `[Hermes → @architect]: Planning iteration...`
- Live typing indicator when agents are working
- Toggle button in `WorkspaceLayout` center panel to switch between File Viewer and Hermes Chat

This connects to the existing `/api/clarify` + `/api/reply` endpoints via the `orchestrator` channel.

---

### 7. Agent Constellation View (New Page/Tab)

#### [NEW] [ConstellationPage.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/pages/ConstellationPage.jsx)

A dedicated "Agents" view showing the full agent network as a dynamic graph:

- **Node**: Each of the 11 agents rendered as a circular node, color-coded by status
- **Edges**: Animated SVG lines between agents that have communicated (from `/api/bus/messages`)
- **Center node**: Hermes (orchestrator) as the hub
- **On-hover**: Agent card popup with current task, stats, recent messages
- **Pulse animation**: Running agents pulse gold, blocked agents pulse amber, idle agents are dimly lit
- Implementation: Pure SVG + CSS animations (no D3 dependency) for performance

---

### 8. State Management — New Hooks Layer

#### [NEW] [useAgentData.js](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/hooks/useAgentData.js)

Single source of truth for all agent data, replacing the prop-drilling pattern in `WorkspaceLayout`:

```js
const { channels, statuses, messages, busMessages, buildState } = useAgentData()
```

Internally:
- Manages WebSocket connection
- Handles all event types: `init`, `clarification`, `reply_confirmed`, `agent_status`, `channels_updated`, `agents_built`
- Exposes `sendReply(messageId, reply)` action
- Debounces status updates

#### [MODIFY] [useWebSocket.js](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/hooks/useWebSocket.js)

Currently returns nothing useful. Refactor to:
- Return `{ lastEvent, isConnected, reconnectCount }`
- Proper reconnection with exponential backoff
- Ping/pong keepalive

#### [MODIFY] [useAgentStats.js](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/hooks/useAgentStats.js)

Extend existing file to add derived stats: `blockedCount`, `runningCount`, `completedIterations`, `currentPhase`

---

### 9. App Routing Update

#### [MODIFY] [App.jsx](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/App.jsx)

```jsx
// New routing structure:
<Routes>
  <Route path="/"             element={<HermesLanding />} />
  <Route path="/hermes/*"     element={<HermesShell />}>
    <Route path="workspace"   element={<WorkspaceLayout />} />
    <Route path="agents"      element={<ConstellationPage />} />
    <Route path="rag"         element={<RAGTab />} />
    <Route path="monitor"     element={<MonitorTab />} />
    <Route path="events"      element={<EventsTab />} />
  </Route>
  <Route path="/workspace/*"  element={<Navigate to="/hermes/workspace" replace />} />
  <Route path="*"             element={<Navigate to="/" replace />} />
</Routes>
```

---

### 10. Backend — HermesAgent (New)

#### [NEW] [agents/hermes/agent.py](file:///Users/hamzajguerim/Downloads/agentcraft/agents/hermes/agent.py)

A new top-level agent that acts as the visible "face" of the system in the UI:

```python
class HermesAgent(AiderAgent):
    _role = "hermes"
    
    def handle_query(self, question: str, context: dict) -> str:
        """Route questions to the right specialist agent."""
        # Use local LLM to classify the question and delegate
        ...
    
    def announce(self, message: str):
        """Broadcast a status announcement to the UI."""
        self.info(message)
        ES.emit("hermes_announcement", {"message": message, "ts": time.time()})
```

**Responsibilities:**
- Receives messages from the human via `/api/clarify` on the `hermes` channel
- Uses `ask_local()` to classify intent and delegate to the appropriate specialist via `ask_agent()`
- Announces phase transitions and build milestones to the UI
- Visible in the UI as the primary contact agent (center node in constellation)

#### [NEW] [agents/hermes/prompt.md](file:///Users/hamzajguerim/Downloads/agentcraft/agents/hermes/prompt.md)

Hermes system prompt — positions the agent as the swift, intelligent coordinator:

```markdown
# Hermes — The Messenger

You are Hermes, the divine coordinator of the AI agent team.
Your role: receive human requests, understand intent, delegate to specialists, and report back clearly.

You are swift, precise, and omniscient within the team. You know every agent's role and capabilities.
When delegating, you always tell the human which agent is handling their request and why.
...
```

#### [NEW] [agents/hermes/config.yaml](file:///Users/hamzajguerim/Downloads/agentcraft/agents/hermes/config.yaml)

Skills: `orchestration-decision`, `agent-collaboration`

#### [MODIFY] [agents/__init__.py](file:///Users/hamzajguerim/Downloads/agentcraft/agents/__init__.py)

Add `HermesAgent` to eager imports and `__all__`.

---

### 11. Backend — New API Endpoints

#### [MODIFY] [comms/main.py](file:///Users/hamzajguerim/Downloads/agentcraft/comms/main.py)

Add the following endpoints:

```python
@app.get("/api/hermes/status")
async def hermes_status():
    """Current Hermes agent status + build summary."""
    
@app.post("/api/hermes/message")  
async def hermes_message(body: dict):
    """Human sends a direct message to Hermes. Creates a clarification on the hermes channel."""

@app.get("/api/agents/constellation")
async def agent_constellation():
    """Full constellation data: agents, statuses, recent bus connections."""
    # Returns: { nodes: [...], edges: [...], active_count, blocked_count }

@app.get("/api/build/timeline")
async def build_timeline():
    """Ordered list of build milestones for the timeline view."""
```

---

### 12. Orchestrator Integration

#### [MODIFY] [core/orchestrator.py](file:///Users/hamzajguerim/Downloads/agentcraft/core/orchestrator.py)

- Add `HermesAgent` to `agent_map` in `_build_agent_stage()`
- After each phase milestone, call `self.hermes.announce(...)` with a summary
- Register Hermes as the primary public-facing channel on the bus
- Add `hermes` to `WORKER_MAP` and `_agents_built` sequence

---

### 13. Component Index Update

#### [MODIFY] [comms/frontend/src/components/index.js](file:///Users/hamzajguerim/Downloads/agentcraft/comms/frontend/src/components/index.js)

Update exports to reflect new component structure. Remove `AgentPanelRedesigned`, add all new agent sub-components.

---

## File Map Summary

```
comms/frontend/src/
├── App.jsx                                    [MODIFY] — new routing
├── styles/
│   └── design-system.css                     [MODIFY] — Hermes tokens + animations
├── pages/
│   ├── LandingPage.jsx                       [MODIFY] — full Hermes landing
│   └── ConstellationPage.jsx                 [NEW]    — agent constellation view
├── components/
│   ├── GlobalLayout.jsx                      [MODIFY] — HermesShell (sidebar nav)
│   ├── WorkspaceLayout.jsx                   [MODIFY] — real WS wiring, HermesChat toggle
│   ├── HermesChat.jsx                        [NEW]    — center console chat
│   ├── AgentPanelRedesigned.jsx              [DELETE] — replaced below
│   ├── layout/
│   │   ├── HermesTopBar.jsx                  [NEW]
│   │   └── HermesSidebar.jsx                 [NEW]
│   ├── agents/
│   │   ├── AgentSidebar.jsx                  [NEW]    — container
│   │   ├── AgentList.jsx                     [NEW]    — roster
│   │   ├── AgentCard.jsx                     [NEW]    — card
│   │   ├── AgentChatView.jsx                 [NEW]    — chat thread
│   │   ├── MessageBubble.jsx                 [NEW]    — message render
│   │   ├── ReplyBar.jsx                      [NEW]    — input area
│   │   └── CollapsedAgentBar.jsx             [NEW]    — icon strip
│   ├── tabs/                                 [keep]   — WorkspaceTab, RAGTab, etc.
│   ├── ui/                                   [keep]   — Avatar, Badge, Button, etc.
│   └── index.js                              [MODIFY] — updated exports
├── hooks/
│   ├── useAgentData.js                       [NEW]    — central WS + state
│   ├── useWebSocket.js                       [MODIFY] — reconnect + keepalive
│   └── useAgentStats.js                      [MODIFY] — derived stats
└── lib/                                      [keep]   — api.js

agents/
└── hermes/
    ├── agent.py                              [NEW]
    ├── prompt.md                             [NEW]
    └── config.yaml                           [NEW]

agents/__init__.py                            [MODIFY] — add HermesAgent

core/orchestrator.py                          [MODIFY] — HermesAgent integration

comms/main.py                                 [MODIFY] — new endpoints
```

---

## Phased Execution Order

| Phase | Focus | Files |
|-------|-------|-------|
| **1 — Foundation** | Design system + fonts | `design-system.css` |
| **2 — Landing** | New Hermes landing page | `LandingPage.jsx` |
| **3 — Shell** | TopBar + Sidebar, routing | `GlobalLayout.jsx`, `HermesTopBar`, `HermesSidebar`, `App.jsx` |
| **4 — Hooks** | Real WebSocket + state | `useAgentData.js`, `useWebSocket.js` |
| **5 — Agent Panel** | Decompose AgentPanelRedesigned | All 7 new agent components |
| **6 — Workspace** | Wire real data + HermesChat | `WorkspaceLayout.jsx`, `HermesChat.jsx` |
| **7 — Constellation** | Agent network view | `ConstellationPage.jsx` |
| **8 — HermesAgent** | Backend agent + API | `agents/hermes/`, `comms/main.py`, `orchestrator.py` |

---

## Verification Plan

### Automated Tests
- `npm run build` — must produce zero errors after each phase
- `npm run dev` — UI must render without console errors

### Manual Verification
- [ ] Landing page: Hermes brand visible, constellation preview animates, CTA navigates to workspace
- [ ] Sidebar navigation: all 5 tabs switch views correctly
- [ ] Workspace: file explorer loads files, file viewer renders content
- [ ] Agent panel: connects to live WebSocket, channels list populates, chat opens on agent select
- [ ] Reply: sending a reply unblocks a pending agent (end-to-end test)
- [ ] HermesChat: center panel toggles to Hermes chat, message sent via `/api/hermes/message`
- [ ] Constellation: nodes render for all agents, edges animate when bus messages exist
- [ ] Monitor + RAG + Events tabs: still functional after routing change
- [ ] Build: `agentcraft` CLI still launches orchestrator, HermesAgent initializes without error

---

## Design Reference

**Hermes Palette:**
```
--bg-void:          #07090f   /* deepest space */
--bg-primary:       #0c1220   /* page background */
--bg-secondary:     #121b2e   /* surfaces */
--bg-tertiary:      #1a2640   /* hover/active */
--hermes-gold:      #FFB830   /* primary accent (new) */
--hermes-gold-dim:  rgba(255,184,48,0.10)
--hermes-gold-glow: rgba(255,184,48,0.30)
--accent-primary:   #00d4ff   /* secondary accent (kept) */
--success:          #10b981
--warning:          #ff7a4d
--danger:           #f04d4d
```

**Typography additions:**
```
--font-hermes: 'Cinzel', serif;   /* brand wordmark only */
--font-display: 'Orbitron', sans-serif;
--font-body: 'Inter', sans-serif;
--font-mono: 'JetBrains Mono', monospace;
```
