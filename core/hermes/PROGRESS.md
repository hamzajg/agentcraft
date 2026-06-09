# Hermes Implementation Progress

## Current Structure (Integrated into AgentCraft)

Hermes is now fully integrated into the AgentCraft project:

### Backend (`core/hermes/`)
```
core/hermes/
├── __init__.py          # Package init
├── models.py            # SQLModel schemas (AgentDefinition, AgentRun, Event)
├── database.py          # SQLite (dev) / PostgreSQL (prod) setup
├── factory.py           # AgentFactory + BaseAgent + RawAgent
├── runner.py            # AgentRunner (sync/async/stream execution)
├── event_bus.py         # In-process asyncio EventBus
├── llm/
│   ├── __init__.py      # BaseLLMProvider, Message, LLMResponse
│   ├── factory.py       # ProviderFactory
│   ├── openai_provider.py
│   └── ollama_provider.py
├── frameworks/
│   └── __init__.py      # LangChain adapter
├── agents/
│   ├── __init__.py      # YAML schema and loader
│   └── examples/
│       └── researcher.yaml
├── skills/              # (Phase 2)
├── mcp/                 # (Phase 3)
└── plugins/             # (Phase 5)
```

### API Routes (`comms/hermes_routes.py`)
All Hermes endpoints are mounted under `/api/hermes/`:
```
GET    /api/hermes/health
POST   /api/hermes/agents
GET    /api/hermes/agents
GET    /api/hermes/agents/{id}
PUT    /api/hermes/agents/{id}
DELETE /api/hermes/agents/{id}
POST   /api/hermes/runs
GET    /api/hermes/runs
GET    /api/hermes/runs/{id}
GET    /api/hermes/runs/{id}/events
GET    /api/hermes/runs/{id}/stream   (SSE)
```

### Frontend (`comms/frontend/src/hermes/`)
```
comms/frontend/src/hermes/
├── components/
│   └── HermesLayout.jsx    # Main layout with tab navigation
├── pages/
│   ├── HermesDashboard.jsx # Dashboard with stats and quick actions
│   ├── HermesAgents.jsx    # Agent list, create/edit/run
│   └── HermesRuns.jsx      # Run list with event log sidebar
├── hooks/
│   └── useRunStream.js     # SSE hook for live run events
├── stores/
│   └── runStore.js         # Zustand store for active run state
└── lib/
    └── api.js              # Typed API client
```

### Access Points
- **Landing Page**: Click "Hermes" button → `/hermes`
- **Direct URL**: `http://localhost:7000/hermes`
- **API**: `http://localhost:7000/api/hermes/*`

---

## Phase 1 — Foundation (Weeks 1–4) ✅ COMPLETE

**Goal:** Working agent runner with basic UI and two LLM providers.

### Backend

- [x] FastAPI scaffold with SQLite + SQLModel
- [x] AgentDefinition schema (YAML + Pydantic)
- [x] AgentFactory (raw + LangChain adapters)
- [x] AgentRunner (sync + async modes)
- [x] EventBus (in-process asyncio)
- [x] SSE stream endpoint `/api/hermes/runs/{id}/stream`
- [x] OpenAI + Ollama providers
- [x] Integrated into comms server (port 7000)

### Frontend

- [x] React + Vite + Tailwind scaffold (in comms)
- [x] Basic agent list + run launcher UI
- [x] Hermes tab in main navigation
- [x] Dashboard with stats
- [x] Agent CRUD + run modal
- [x] Run list with event log sidebar

---

## Phase 2 — Multi-LLM + Skills (Weeks 5–8)

- [ ] Anthropic, Gemini, Groq providers
- [ ] Provider fallback chain
- [ ] Skill system (tool skills + prompt skills)
- [ ] 5 built-in skills: web_search, code_exec, file_reader, http_client, formatter
- [ ] Mid-system prompt injection
- [ ] Template variables in prompts
- [ ] Agent builder UI (full prompt editor, skill picker)
- [ ] Run history + event log UI

---

## Phase 3 — MCP + Framework Adapters (Weeks 9–12)

- [ ] MCP client (SSE + stdio)
- [ ] MCP registry + tool auto-discovery
- [ ] MCP picker in agent builder UI
- [ ] CrewAI adapter
- [ ] AutoGen adapter
- [ ] LlamaIndex adapter
- [ ] Framework selector in UI
- [ ] Redis-backed EventBus (production mode)

---

## Phase 4 — Pipelines + Multi-Agent (Weeks 13–16)

- [ ] Pipeline YAML schema + DAG executor
- [ ] Fan-out/fan-in execution
- [ ] Pub/sub agent collaboration
- [ ] Supervisor / sub-agent spawning
- [ ] WebSocket endpoint for bidirectional comms
- [ ] Human-in-the-loop pause/resume
- [ ] Visual pipeline designer (drag-and-drop)
- [ ] Animated edge streaming in graph

---

## Phase 5 — Plugins + Marketplace (Weeks 17–20)

- [ ] Plugin manifest + validation
- [ ] Plugin runtime (sandboxed execution)
- [ ] Plugin types: tool_skill, prompt_skill, framework_adapter
- [ ] Local plugin loader
- [ ] Marketplace registry (self-hosted)
- [ ] Plugin search + install UI
- [ ] Plugin version management

---

## Phase 6 — Production Hardening (Weeks 21–24)

- [ ] PostgreSQL + Alembic migrations
- [ ] JWT auth + API keys
- [ ] Rate limiting
- [ ] Celery task queue (optional heavy mode)
- [ ] LM Studio + Azure OpenAI + Cohere providers
- [ ] HuggingFace + smolagents + PydanticAI adapters
- [ ] Docker Compose (full stack)
- [ ] Hermes CLI (run, deploy, marketplace commands)
- [ ] Comprehensive test suite

---

## Database Configuration

- **Development**: SQLite at `comms/hermes.db`
- **Production**: PostgreSQL via `HERMES_DATABASE_URL` env var

```bash
# Production setup
export HERMES_DATABASE_URL="postgresql://user:pass@localhost:5432/hermes"
```

## Running

```bash
# Backend (comms server with Hermes)
cd comms
uvicorn main:app --port 7000 --reload

# Frontend
cd comms/frontend
npm install
npm run dev
```
