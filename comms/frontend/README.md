# Agent Comms — React Frontend

React 18 + Tailwind CSS chat interface for agent↔human & agent↔agent communication.

## Dev mode (hot reload)

```bash
cd comms-server/frontend
npm install
npm run dev          # → http://localhost:5173
                     # proxies /api and /ws to FastAPI on :7000
```

Run FastAPI backend at the same time:

```bash
cd comms-server
uvicorn main:app --port 7000 --reload
```

## Production build

Builds into `comms-server/static/` — served directly by FastAPI.

```bash
cd comms-server/frontend
npm run build
```

After building, `http://localhost:7000` serves the compiled app.

## Stack

| | |
|---|---|
| Framework | React 18 |
| Styling | Tailwind CSS 3 |
| Bundler | Vite 5 |
| Fonts | IBM Plex Sans + IBM Plex Mono |
| Real-time | WebSocket (auto-reconnect) |
| Date formatting | date-fns |

## Component tree

```
App
├── Header        — connection status, pending badge
├── Sidebar       — agent channels, status dots, unread badges
└── Main panel
    ├── ChannelHeader — active agent name + status
    ├── Message list
    │   ├── AgentBubble   — question, file pill, partial output, suggestion chips
    │   └── YouBubble     — your reply
    └── ReplyBar          — textarea, Send button, Enter to send
```

## WebSocket events handled

| Event | Action |
|-------|--------|
| `init` | Load channels + pending messages |
| `clarification` | Add message, increment unread, flash title |
| `reply_confirmed` | Mark message replied, decrement pending count |
| `agent_status` | Update sidebar status dot |
