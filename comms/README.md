# Agent Comms Server

The human-facing communication layer for the AI agent team. Agents send messages here when they hit a blocker or need clarification. You reply in the chat UI and they resume automatically.

## How it works

```
Agent hits blocker
  → POST /api/clarify  { question, file, partial_output, suggestions }
  → Agent thread suspends (blocks on reply)
  → UI receives message via WebSocket instantly
  → You type a reply and hit Send
  → Agent resumes with your reply injected into its prompt
```

## Start

```bash
cd comms-server
pip install -r requirements.txt
uvicorn main:app --port 7000 --reload

# Open the UI
open http://localhost:7000
```

## UI features

- **Channel sidebar** — one channel per agent, with unread badge and live status dot
- **Message thread** — each message shows the question, the file being worked on, and partial output the agent has produced so far
- **Suggestion chips** — click an agent's own suggestion to pre-fill the reply box
- **Real-time** — WebSocket delivers messages instantly, no polling
- **Persistent history** — SQLite stores all messages across server restarts

## Status dots

| Colour | Meaning |
|--------|---------|
| Green (pulsing) | Agent actively running |
| Amber (pulsing) | Agent blocked — waiting for your reply |
| Grey | Agent idle |

## Phase 2 — Slack and Teams

Set environment variables to receive notifications when agents need input, even if the UI is not open:

```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
export TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

The notification includes a deep link directly to the relevant message in the UI.

## Ports

| Service | Port |
|---------|------|
| Comms server + UI | 7000 |
| Ollama | 11434 |

## Agent integration

Any agent can ask a question with one call:

```python
# In any agent class (already wired via base.py):
reply = self.ask(
    question="Should I use ConcurrentHashMap or synchronized List?",
    file=task["file"],
    partial_output=current_code,
    suggestions=["ConcurrentHashMap keyed by stepIndex", "synchronized ArrayList"],
)
# Agent blocks here until you reply in the UI
# reply contains your text
```

The comms server is optional — if it is not running, `ask()` returns the first suggestion immediately and the agent continues without blocking.
