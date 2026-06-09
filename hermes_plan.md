# Hermes — Agnostic AI Agent Factory & Runner
### A Sub-Project of [AgentCraft](https://github.com/hamzajg/agentcraft)

> **Hermes** (Greek messenger god) — lightweight, fast, and universal. An agnostic factory and runner for AI agents with real-time visualization, multi-LLM support, event streaming, and a plugin marketplace.

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Tech Stack](#3-tech-stack)
4. [Core Concepts](#4-core-concepts)
5. [Backend — Python / FastAPI](#5-backend--python--fastapi)
6. [Frontend — React / TypeScript / TailwindCSS](#6-frontend--react--typescript--tailwindcss)
7. [Agent Input Model](#7-agent-input-model)
8. [LLM Provider Layer](#8-llm-provider-layer)
9. [Agentic Framework Adapters](#9-agentic-framework-adapters)
10. [Skills System](#10-skills-system)
11. [MCP Integration](#11-mcp-integration)
12. [Plugin & Marketplace System](#12-plugin--marketplace-system)
13. [Multi-Agent Collaboration](#13-multi-agent-collaboration)
14. [Event Streaming (Sync & Async)](#14-event-streaming-sync--async)
15. [Real-Time Nodes Grid Visualization](#15-real-time-nodes-grid-visualization)
16. [Repository Structure](#16-repository-structure)
17. [API Reference](#17-api-reference)
18. [Data Models](#18-data-models)
19. [Phase Roadmap](#19-phase-roadmap)
20. [Integration with AgentCraft](#20-integration-with-agentcraft)

---

## 1. Vision & Goals

Hermes is a **lightweight, framework-agnostic** runtime for building, running, and visualizing AI agents. It sits inside AgentCraft as the universal execution engine — separate from AgentCraft's doc-to-code workflow, but reusable by it.

**Core goals:**

- **Factory**: define an agent once (config + prompts + skills), spawn N instances
- **Runner**: execute agents synchronously, asynchronously, or in streaming mode
- **Agnostic**: works with any LLM provider (OpenAI, Anthropic, Gemini, Groq, Ollama, LM Studio, …) and any agentic framework (LangChain, LlamaIndex, CrewAI, AutoGen, Haystack, raw API)
- **Observable**: real-time node graph showing agents, messages, tools, decisions, and state
- **Extensible**: skills, plugins, MCP servers, and a marketplace — no code changes to core
- **Collaborative**: multi-agent pipelines with typed events, topic-based pub/sub, and DAG execution

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          HERMES                                     │
│                                                                     │
│  ┌──────────────────┐     ┌──────────────────┐   ┌──────────────┐  │
│  │   Hermes Studio  │     │   Hermes API     │   │  Hermes CLI  │  │
│  │  (React/TS/TW)   │◄───►│  (FastAPI)       │◄──│  (Python)    │  │
│  └──────────────────┘     └────────┬─────────┘   └──────────────┘  │
│                                    │                                │
│           ┌────────────────────────┼───────────────────────┐        │
│           │                        │                       │        │
│    ┌──────▼──────┐   ┌─────────────▼──────┐   ┌───────────▼────┐   │
│    │   Agent     │   │   Execution        │   │   Event Bus    │   │
│    │   Factory   │   │   Engine           │   │   (SSE/WS)     │   │
│    └──────┬──────┘   └─────────────┬──────┘   └───────────┬────┘   │
│           │                        │                       │        │
│    ┌──────▼──────────────────────  │  ──────────────────── ▼────┐   │
│    │              Plugin & Skill Runtime                        │   │
│    └────┬──────────────────────────────────────────┬───────────┘   │
│         │                                          │               │
│  ┌──────▼───────┐   ┌───────────────┐   ┌─────────▼──────────┐    │
│  │  LLM Router  │   │ MCP Registry  │   │  Framework Adapter │    │
│  │  (multi-llm) │   │ (MCP servers) │   │  (LangChain, Crew) │    │
│  └──────────────┘   └───────────────┘   └────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Layers

| Layer | Responsibility |
|---|---|
| **Agent Factory** | Parse agent config, instantiate agent objects, manage lifecycle |
| **Execution Engine** | Sync/async task runner, retry logic, timeout, checkpointing |
| **LLM Router** | Normalize calls across providers; model fallback chains |
| **Framework Adapter** | Wrap LangChain, CrewAI, AutoGen, etc. under a unified interface |
| **Event Bus** | Typed events dispatched to all subscribers via SSE/WebSocket |
| **Plugin Runtime** | Load, validate, sandbox, and execute plugins and marketplace items |
| **MCP Registry** | Discover, connect, and proxy MCP servers per agent |
| **Hermes Studio** | React UI: agent builder, run monitor, node graph visualization |

---

## 3. Tech Stack

### Backend

| Concern | Choice | Rationale |
|---|---|---|
| API Framework | **FastAPI** | Async native, SSE/WebSocket support, auto OpenAPI docs |
| Language | **Python 3.12+** | Compatible with all agentic frameworks |
| Task Queue | **asyncio + anyio** (lightweight) / **Celery** (optional heavy mode) | Keep it light by default |
| Event Bus | **Redis Streams** (prod) / **in-process asyncio Queue** (dev) | Progressive enhancement |
| Database | **SQLite** (dev) / **PostgreSQL** (prod) via SQLModel | Config, run history, marketplace |
| Agent State | **Redis** or **in-memory** depending on deploy mode | Agent memory and checkpointing |
| Auth | **JWT + API keys** | Simple, stateless |
| Config | **YAML / JSON** + Pydantic models | Matches AgentCraft workspace.yaml style |

### Frontend

| Concern | Choice |
|---|---|
| Framework | **React 18 + TypeScript** |
| Styling | **TailwindCSS v4** |
| Node Visualization | **React Flow (xyflow)** — real-time node graph |
| State | **Zustand** (lightweight) |
| Data Fetching | **TanStack Query** + native `EventSource` for SSE |
| Forms | **React Hook Form + Zod** |
| Icons | **Lucide React** |
| Build | **Vite** |

### Infrastructure (Optional / Docker Compose)

```yaml
services:
  hermes-api:     # FastAPI backend
  hermes-studio:  # React frontend
  redis:          # Event bus + agent state
  postgres:       # Persistent storage (optional)
  ollama:         # Local LLM server
```

---

## 4. Core Concepts

### Agent Definition

An agent in Hermes is a **portable configuration** — not a class hierarchy. Defined as YAML or JSON:

```yaml
# agents/my-researcher/agent.yaml
id: researcher-001
name: Research Agent
description: Searches and summarizes information

# Prompt inputs (see Section 7)
prompt:
  system: "You are a research assistant..."
  mid_system: null
  user_template: "Research the following topic: {{topic}}"

# LLM provider binding
llm:
  provider: openai          # or anthropic, ollama, groq, gemini, ...
  model: gpt-4o-mini
  temperature: 0.3
  fallback:
    - provider: ollama
      model: llama3.2

# Agentic framework to use
framework: langchain        # or crewai, autogen, llamaindex, raw, ...

# Skills attached to this agent
skills:
  - web-search
  - markdown-formatter

# MCP servers this agent can access
mcp_servers:
  - name: brave-search
    url: https://mcp.brave.com/sse
  - name: filesystem
    path: /var/data

# Plugins from marketplace
plugins:
  - id: hermes/pdf-extractor@1.2.0

# Collaboration config
collaboration:
  can_spawn: true           # can create sub-agents
  topics:                   # pub/sub topics this agent listens on
    - research.results
  emits:
    - research.complete
```

### Run

A **Run** is a single execution of one or more agents against a set of inputs. Runs have:
- unique `run_id`
- input payload
- execution graph (which agents ran, in what order)
- event log (every message, tool call, decision)
- final output
- status: `queued | running | paused | complete | failed`

### Pipeline

A **Pipeline** is a DAG of agents. Each node is an agent definition; edges define data flow and trigger conditions.

---

## 5. Backend — Python / FastAPI

### Directory Structure

```
hermes/
├── api/
│   ├── main.py                  # FastAPI app entry point
│   ├── routers/
│   │   ├── agents.py            # CRUD for agent definitions
│   │   ├── runs.py              # start, stop, inspect runs
│   │   ├── pipelines.py         # pipeline CRUD and execution
│   │   ├── providers.py         # LLM provider config
│   │   ├── plugins.py           # plugin install/remove/list
│   │   ├── marketplace.py       # browse and install from marketplace
│   │   ├── mcp.py               # MCP server registration
│   │   ├── events.py            # SSE event stream endpoint
│   │   └── skills.py            # skill library management
│   ├── middleware/
│   │   ├── auth.py
│   │   └── rate_limit.py
│   └── deps.py                  # FastAPI dependencies
│
├── core/
│   ├── factory.py               # AgentFactory — instantiates agents
│   ├── runner.py                # AgentRunner — sync/async/stream execution
│   ├── pipeline.py              # PipelineEngine — DAG executor
│   ├── event_bus.py             # EventBus — pub/sub, SSE dispatch
│   ├── state.py                 # AgentStateManager — Redis/in-mem
│   └── scheduler.py             # Cron/deferred run scheduling
│
├── llm/
│   ├── router.py                # LLMRouter — normalize across providers
│   ├── providers/
│   │   ├── base.py              # BaseLLMProvider (abstract)
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   ├── gemini.py
│   │   ├── groq.py
│   │   ├── ollama.py
│   │   ├── lmstudio.py
│   │   ├── azure_openai.py
│   │   ├── cohere.py
│   │   └── huggingface.py
│   └── fallback.py              # Provider fallback chain logic
│
├── frameworks/
│   ├── base.py                  # BaseFrameworkAdapter (abstract)
│   ├── langchain.py
│   ├── crewai.py
│   ├── autogen.py
│   ├── llamaindex.py
│   ├── haystack.py
│   ├── smolagents.py
│   ├── pydantic_ai.py
│   └── raw.py                   # Direct LLM API, no framework
│
├── skills/
│   ├── base.py                  # BaseSkill
│   ├── loader.py                # SkillLoader — discover and inject
│   └── builtin/
│       ├── web_search.py
│       ├── code_executor.py
│       ├── file_reader.py
│       ├── markdown_formatter.py
│       └── http_client.py
│
├── mcp/
│   ├── registry.py              # MCPRegistry — connect, list, proxy
│   ├── client.py                # MCP SSE/stdio client
│   └── tool_mapper.py           # Map MCP tools → agent tool format
│
├── plugins/
│   ├── runtime.py               # PluginRuntime — load, sandbox, execute
│   ├── validator.py             # Plugin manifest validation
│   └── sandbox.py               # Restricted execution environment
│
├── marketplace/
│   ├── client.py                # Marketplace API client
│   ├── resolver.py              # Dependency resolution
│   └── installer.py             # Download and install packages
│
├── models/                      # SQLModel / Pydantic schemas
│   ├── agent.py
│   ├── run.py
│   ├── pipeline.py
│   ├── event.py
│   ├── provider.py
│   └── plugin.py
│
├── db/
│   ├── session.py
│   └── migrations/
│
└── config.py                    # Settings (pydantic-settings)
```

### Key Backend Patterns

**AgentFactory**
```python
class AgentFactory:
    def create(self, definition: AgentDefinition) -> HermesAgent:
        """Instantiate an agent from its definition YAML/dict."""
        llm = self.llm_router.resolve(definition.llm)
        framework = self.framework_registry.get(definition.framework)
        skills = self.skill_loader.load(definition.skills)
        mcp_tools = self.mcp_registry.get_tools(definition.mcp_servers)
        return framework.build(definition, llm, skills + mcp_tools)
```

**AgentRunner**
```python
class AgentRunner:
    async def run(self, agent: HermesAgent, input: RunInput) -> RunResult:
        """Execute agent; emit events throughout."""

    async def run_stream(self, agent: HermesAgent, input: RunInput) -> AsyncIterator[Event]:
        """Stream token-by-token and tool events."""

    async def run_pipeline(self, pipeline: Pipeline, inputs: dict) -> PipelineResult:
        """Execute a DAG of agents with dependency resolution."""
```

**EventBus**
```python
class EventBus:
    async def publish(self, event: HermesEvent) -> None: ...
    async def subscribe(self, run_id: str) -> AsyncIterator[HermesEvent]: ...
    async def subscribe_topic(self, topic: str) -> AsyncIterator[HermesEvent]: ...
```

---

## 6. Frontend — React / TypeScript / TailwindCSS

### Directory Structure

```
hermes-studio/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   └── routes/
│   │       ├── index.tsx          # Dashboard
│   │       ├── agents/            # Agent builder + library
│   │       ├── runs/              # Run history + live monitor
│   │       ├── pipelines/         # Visual pipeline editor
│   │       ├── providers/         # LLM provider settings
│   │       ├── plugins/           # Plugin manager
│   │       ├── marketplace/       # Browse + install
│   │       └── settings/
│   │
│   ├── components/
│   │   ├── agent-builder/
│   │   │   ├── PromptEditor.tsx   # system/user/mid-system prompts
│   │   │   ├── SkillPicker.tsx
│   │   │   ├── MCPPicker.tsx
│   │   │   ├── ProviderSelector.tsx
│   │   │   └── FrameworkSelector.tsx
│   │   │
│   │   ├── visualization/
│   │   │   ├── AgentGraph.tsx     # React Flow node graph
│   │   │   ├── AgentNode.tsx      # Single node component
│   │   │   ├── EdgeStream.tsx     # Animated edge for active streams
│   │   │   ├── EventLog.tsx       # Sidebar: live event feed
│   │   │   └── ToolCallNode.tsx   # Tool invocation visualization
│   │   │
│   │   ├── run-monitor/
│   │   │   ├── RunStatus.tsx
│   │   │   ├── TokenCounter.tsx
│   │   │   └── StreamOutput.tsx
│   │   │
│   │   ├── marketplace/
│   │   │   ├── PluginCard.tsx
│   │   │   └── PluginInstaller.tsx
│   │   │
│   │   └── ui/                    # Shared primitive components
│   │
│   ├── hooks/
│   │   ├── useRunStream.ts        # SSE hook for live run events
│   │   ├── useAgentGraph.ts       # Build React Flow graph from run state
│   │   └── useMarketplace.ts
│   │
│   ├── stores/
│   │   ├── runStore.ts            # Zustand: active run state
│   │   ├── agentStore.ts
│   │   └── graphStore.ts          # Node positions + edge state
│   │
│   ├── lib/
│   │   ├── api.ts                 # Typed API client
│   │   ├── sse.ts                 # EventSource wrapper
│   │   └── schemas.ts             # Zod schemas matching backend Pydantic
│   │
│   └── types/
│       ├── agent.ts
│       ├── run.ts
│       └── events.ts
│
├── public/
├── tailwind.config.ts
├── vite.config.ts
└── tsconfig.json
```

---

## 7. Agent Input Model

Hermes supports three prompt injection points, matching the AgentCraft conventions and extending them:

### Prompt Layers

```
┌────────────────────────────────────────────┐
│  SYSTEM PROMPT                             │  ← Agent identity, rules, persona
│  (static, set at definition time)          │
├────────────────────────────────────────────┤
│  MID-SYSTEM PROMPT                         │  ← Dynamic context injection
│  (injected at runtime per request)         │  ← e.g. current date, user role,
│  (can be skill output or pipeline context) │    retrieved memory, RAG results
├────────────────────────────────────────────┤
│  USER PROMPT                               │  ← The actual task / query
│  (template or raw string)                  │
└────────────────────────────────────────────┘
```

### How Mid-System Prompts Work

Mid-system prompts allow dynamic context to be injected between the static system prompt and the user message without modifying the agent definition. They are ideal for:

- Injecting RAG-retrieved documents
- Passing pipeline context from a previous agent
- Adding runtime constraints (e.g., "today is June 2026, user is admin")
- Skill outputs that should inform reasoning

```python
# Backend: RunInput model
class RunInput(BaseModel):
    user_prompt: str
    mid_system_prompt: str | None = None     # dynamic injection
    variables: dict = {}                      # template substitution
    context: dict = {}                        # arbitrary metadata
```

### Prompt Template Variables

User prompts and mid-system prompts support `{{variable}}` templating:

```yaml
user_template: "Analyze the following code:\n\n{{code}}\n\nFocus on: {{focus_area}}"
```

---

## 8. LLM Provider Layer

### Provider Registry

```
hermes/llm/providers/
├── openai.py          GPT-4o, GPT-4o-mini, o1, o3, …
├── anthropic.py       Claude 3.5/4 Sonnet, Opus, Haiku
├── gemini.py          Gemini 2.0 Flash, Pro, Ultra
├── groq.py            Llama 3, Mixtral (ultra-fast inference)
├── ollama.py          Any local model via Ollama REST API
├── lmstudio.py        LM Studio local server
├── azure_openai.py    Azure-hosted OpenAI models
├── cohere.py          Command R+
├── huggingface.py     HF Inference API + TGI endpoints
└── together.py        Together AI hosted models
```

### Unified Provider Interface

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse: ...

    @abstractmethod
    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...
```

### Provider Config (YAML)

```yaml
# hermes/providers.yaml
providers:
  - id: local-ollama
    type: ollama
    base_url: http://localhost:11434
    default_model: llama3.2

  - id: openai-prod
    type: openai
    api_key: ${OPENAI_API_KEY}
    default_model: gpt-4o-mini

  - id: anthropic-prod
    type: anthropic
    api_key: ${ANTHROPIC_API_KEY}
    default_model: claude-sonnet-4-6
```

### Fallback Chain

```yaml
llm:
  provider: openai-prod
  model: gpt-4o
  fallback:
    - provider: anthropic-prod
      model: claude-haiku-4-5
    - provider: local-ollama
      model: llama3.2
```

When the primary provider fails (rate limit, timeout, error), Hermes automatically tries the next in the chain. All events include `provider_used` so the UI can show which model actually ran.

---

## 9. Agentic Framework Adapters

### Supported Frameworks

| Framework | Adapter | Notes |
|---|---|---|
| **Raw API** | `raw.py` | Direct LLM calls, no framework overhead |
| **LangChain** | `langchain.py` | Full tool/chain/agent support |
| **LlamaIndex** | `llamaindex.py` | RAG-heavy agents, query engines |
| **CrewAI** | `crewai.py` | Role-based multi-agent crews |
| **AutoGen** | `autogen.py` | Conversational multi-agent |
| **Haystack** | `haystack.py` | Pipeline-first, document processing |
| **smolagents** | `smolagents.py` | HuggingFace lightweight agents |
| **PydanticAI** | `pydantic_ai.py` | Type-safe structured output agents |
| **AgentCraft** | `agentcraft.py` | Native adapter for parent project |

### Adapter Interface

```python
class BaseFrameworkAdapter(ABC):
    @abstractmethod
    def build(
        self,
        definition: AgentDefinition,
        llm: BaseLLMProvider,
        tools: list[Tool],
    ) -> HermesAgent: ...

    @abstractmethod
    async def execute(
        self,
        agent: HermesAgent,
        input: RunInput,
        event_bus: EventBus,
    ) -> RunResult: ...
```

Each adapter wraps the framework's native runner and normalizes events into Hermes's `HermesEvent` format, so the visualization layer works identically regardless of which framework runs the agent.

---

## 10. Skills System

Skills are **reusable, injectable capabilities** — functions, API calls, or prompt augmentations — that any agent can use without modifying the core agent definition.

### Skill Types

| Type | Description | Example |
|---|---|---|
| **Tool Skill** | Exposes a Python function as an LLM tool | `web_search`, `code_exec` |
| **Prompt Skill** | Injects text into mid-system prompt | `coding-standards`, `json-output-format` |
| **Pipeline Skill** | Triggers sub-agents or transformations | `summarize_output`, `translate_to_french` |

### Skill Definition

```python
# skills/builtin/web_search.py
from hermes.skills import skill, ToolSkill

@skill(
    id="web-search",
    name="Web Search",
    description="Search the web for current information",
    version="1.0.0",
)
class WebSearchSkill(ToolSkill):
    async def execute(self, query: str) -> str:
        """Search the web and return a summary."""
        ...
```

### Skills in Agent Config

```yaml
skills:
  - web-search           # builtin
  - coding-standards     # prompt skill from skills/ folder
  - hermes/pdf-reader    # from marketplace
  - ./my-custom-skill    # local custom skill
```

---

## 11. MCP Integration

Hermes connects agents to **Model Context Protocol** servers, turning any MCP-compatible service into agent tools automatically.

### MCP Registry

```python
class MCPRegistry:
    async def register(self, server: MCPServerConfig) -> None: ...
    async def list_tools(self, server_id: str) -> list[MCPTool]: ...
    async def call_tool(self, server_id: str, tool: str, args: dict) -> Any: ...
    async def get_agent_tools(self, server_ids: list[str]) -> list[Tool]: ...
```

### Agent MCP Config

```yaml
mcp_servers:
  - name: brave-search
    type: sse
    url: https://mcp.brave.com/sse
    auth:
      type: bearer
      token: ${BRAVE_MCP_TOKEN}

  - name: filesystem
    type: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]

  - name: postgres
    type: sse
    url: http://localhost:5173/sse
```

### MCP Tool Auto-Discovery

When an agent starts, Hermes queries each configured MCP server, retrieves its tool manifest, and automatically injects those tools into the agent's tool list — no manual mapping needed.

---

## 12. Plugin & Marketplace System

### Plugin Manifest (`plugin.yaml`)

```yaml
id: my-org/sentiment-analyzer
name: Sentiment Analyzer
version: 2.1.0
description: Adds sentiment analysis as an agent tool
author: my-org
license: MIT
hermes_version: ">=0.3.0"

provides:
  - type: tool_skill
    id: sentiment-analyze
  - type: prompt_skill
    id: sentiment-aware-tone

install:
  pip: [transformers, torch]

entry: ./plugin.py
```

### Plugin Types

| Type | Description |
|---|---|
| `tool_skill` | Adds a callable tool to agents |
| `prompt_skill` | Injects text into system/mid-system prompts |
| `framework_adapter` | New agentic framework support |
| `llm_provider` | New LLM provider |
| `visualization` | Custom node type in the graph UI |
| `event_handler` | React to agent events (webhooks, logging, etc.) |

### Marketplace Structure

The Hermes Marketplace is a registry (self-hostable) of validated plugins:

```
GET  /marketplace/search?q=pdf&category=tools
GET  /marketplace/plugins/{id}
GET  /marketplace/plugins/{id}/versions
POST /marketplace/plugins/{id}/install
DEL  /marketplace/plugins/{id}/uninstall
```

Plugins can be sourced from:
- **Hermes Official Registry** (curated)
- **GitHub** (`hamzajg/hermes-plugin-{name}`)
- **Local path** (`./my-plugin`)
- **Private registry** (self-hosted)

---

## 13. Multi-Agent Collaboration

### Collaboration Patterns

**Sequential Pipeline (Chain)**
```
Agent A → Agent B → Agent C → Output
```
Each agent receives the output of the previous one as its input.

**Parallel Fan-Out / Fan-In**
```
          ┌→ Agent B ─┐
Input → A ┤            ├→ Merge → Output
          └→ Agent C ─┘
```
Multiple agents run in parallel; results are merged by a coordinator.

**Event-Driven (Pub/Sub)**
```
Agent A emits: research.complete
Agent B listens on: research.complete → starts automatically
Agent C listens on: research.complete → starts automatically
```

**Supervisor / Sub-Agent**
```
Supervisor Agent
    ├── spawns Research Agent
    ├── spawns Drafting Agent
    └── reviews and merges
```

### Pipeline Definition (YAML)

```yaml
# pipelines/research-and-write.yaml
id: research-and-write
name: Research and Write

nodes:
  - id: researcher
    agent: researcher-001
    inputs:
      topic: "{{pipeline.topic}}"

  - id: writer
    agent: writer-001
    inputs:
      research: "{{nodes.researcher.output}}"
    depends_on: [researcher]

  - id: editor
    agent: editor-001
    inputs:
      draft: "{{nodes.writer.output}}"
      style: formal
    depends_on: [writer]

output: "{{nodes.editor.output}}"
```

### Agent-to-Agent Communication

Agents in the same run can communicate directly via typed messages:

```python
# Agent B can send a message directly to Agent A in the same run
await self.send_to("agent-a", AgentMessage(
    type="clarification_request",
    content="What time period should I focus on?",
))
```

---

## 14. Event Streaming (Sync & Async)

### Event Types

```python
class EventType(str, Enum):
    # Lifecycle
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_PAUSED = "run.paused"

    # Agent
    AGENT_STARTED = "agent.started"
    AGENT_THINKING = "agent.thinking"
    AGENT_TOKEN = "agent.token"          # streaming token
    AGENT_COMPLETED = "agent.completed"

    # Tools
    TOOL_CALLED = "tool.called"
    TOOL_RESULT = "tool.result"
    MCP_CALLED = "mcp.called"
    MCP_RESULT = "mcp.result"

    # Pipeline
    PIPELINE_NODE_STARTED = "pipeline.node.started"
    PIPELINE_NODE_COMPLETED = "pipeline.node.completed"

    # Collaboration
    AGENT_MESSAGE_SENT = "agent.message.sent"
    AGENT_MESSAGE_RECEIVED = "agent.message.received"

    # Errors
    ERROR = "error"
    RETRY = "retry"
    FALLBACK_TRIGGERED = "fallback.triggered"
```

### SSE Stream Endpoint

```
GET /api/runs/{run_id}/stream
```

Response is a Server-Sent Events stream:
```
data: {"type":"agent.started","agent_id":"researcher-001","ts":"..."}

data: {"type":"agent.token","agent_id":"researcher-001","token":"The","ts":"..."}

data: {"type":"tool.called","agent_id":"researcher-001","tool":"web_search","args":{"query":"..."},"ts":"..."}

data: {"type":"run.completed","run_id":"...","output":"...","ts":"..."}
```

### WebSocket Alternative

```
WS /api/runs/{run_id}/ws
```

Supports bidirectional communication — useful for human-in-the-loop agents that need to pause and request user input.

### Sync vs Async Execution Modes

| Mode | Endpoint | Use Case |
|---|---|---|
| **Sync** | `POST /api/runs` (waits for result) | Short tasks, testing |
| **Async** | `POST /api/runs/async` → returns `run_id` | Long tasks, production |
| **Stream** | `POST /api/runs/stream` → SSE body | Real-time output display |
| **Pipeline** | `POST /api/pipelines/{id}/run` | Multi-agent DAG |

---

## 15. Real-Time Nodes Grid Visualization

The centerpiece of Hermes Studio is a **live, animated node graph** powered by React Flow.

### Graph Topology

```
[Provider: OpenAI]
        │
        ▼
[Agent: Researcher]──── tool call ────[MCP: brave-search]
        │
        │ emits: research.complete
        ▼
[Agent: Writer]─────── tool call ─────[Skill: markdown-formatter]
        │
        ▼
[Agent: Editor]
        │
        ▼
[Output Node]
```

### Node States (visual encoding)

| State | Visual |
|---|---|
| `idle` | Gray border, no animation |
| `queued` | Dashed border, pulsing |
| `thinking` | Blue border, spinning loader |
| `streaming` | Green border, token counter ticking |
| `tool_calling` | Orange border, tool name badge |
| `waiting` | Yellow border, hourglass icon |
| `completed` | Solid green border, checkmark |
| `failed` | Red border, error badge |
| `fallback` | Purple border, provider switch indicator |

### Edge Types

| Edge | Visual |
|---|---|
| Data flow | Solid arrow |
| Event trigger | Dashed arrow |
| Active streaming | Animated particles along edge |
| Tool call | Orange dashed arrow to tool node |

### Real-Time Updates

The UI subscribes to the SSE stream for the active run and updates the graph on every event:

```typescript
// hooks/useAgentGraph.ts
function useAgentGraph(runId: string) {
  const { nodes, edges, updateNode, addEdge } = useGraphStore();

  useRunStream(runId, (event) => {
    switch (event.type) {
      case 'agent.started':
        updateNode(event.agent_id, { status: 'thinking' });
        break;
      case 'tool.called':
        addEdge(event.agent_id, event.tool, { type: 'tool_call', animated: true });
        break;
      case 'agent.completed':
        updateNode(event.agent_id, { status: 'completed', output: event.output });
        break;
    }
  });

  return { nodes, edges };
}
```

### Visualization Modes

| Mode | Description |
|---|---|
| **Live Run View** | Graph updates in real-time as agents execute |
| **History Replay** | Replay any past run event-by-event |
| **Pipeline Designer** | Drag-and-drop pipeline editor |
| **Debug View** | Expand any node to see full prompt, response, and tool calls |

---

## 16. Repository Structure

```
agentcraft/
└── hermes/                          ← new sub-project
    ├── README.md
    ├── pyproject.toml
    ├── docker-compose.yml
    ├── Makefile
    │
    ├── api/                         ← FastAPI application
    │   └── (see Section 5)
    │
    ├── core/                        ← Factory, Runner, EventBus
    ├── llm/                         ← Provider layer
    ├── frameworks/                  ← Framework adapters
    ├── skills/                      ← Built-in skill library
    ├── mcp/                         ← MCP client + registry
    ├── plugins/                     ← Plugin runtime
    ├── marketplace/                 ← Marketplace client
    ├── models/                      ← Pydantic + SQLModel schemas
    ├── db/                          ← Database sessions + migrations
    ├── config.py
    │
    ├── studio/                      ← React frontend
    │   ├── src/
    │   │   └── (see Section 6)
    │   ├── package.json
    │   ├── vite.config.ts
    │   └── tailwind.config.ts
    │
    ├── agents/                      ← Example agent definitions
    │   ├── researcher/agent.yaml
    │   ├── writer/agent.yaml
    │   └── coder/agent.yaml
    │
    ├── pipelines/                   ← Example pipeline definitions
    │   └── research-and-write.yaml
    │
    └── tests/
        ├── unit/
        ├── integration/
        └── e2e/
```

---

## 17. API Reference

### Agents

```
GET    /api/agents               List all agent definitions
POST   /api/agents               Create agent definition
GET    /api/agents/{id}          Get agent by ID
PUT    /api/agents/{id}          Update agent definition
DELETE /api/agents/{id}          Delete agent
POST   /api/agents/{id}/validate Validate agent config
POST   /api/agents/{id}/test     Quick test run
```

### Runs

```
POST   /api/runs                 Start sync run
POST   /api/runs/async           Start async run → returns run_id
POST   /api/runs/stream          Start streaming run (SSE body)
GET    /api/runs                 List runs (with filters)
GET    /api/runs/{id}            Get run details
GET    /api/runs/{id}/events     Get all events for a run
GET    /api/runs/{id}/stream     SSE stream for live run
WS     /api/runs/{id}/ws         WebSocket for live run
POST   /api/runs/{id}/cancel     Cancel a running job
POST   /api/runs/{id}/pause      Pause (human-in-the-loop)
POST   /api/runs/{id}/resume     Resume paused run
```

### Pipelines

```
GET    /api/pipelines            List pipelines
POST   /api/pipelines            Create pipeline
GET    /api/pipelines/{id}       Get pipeline
PUT    /api/pipelines/{id}       Update pipeline
DELETE /api/pipelines/{id}
POST   /api/pipelines/{id}/run   Execute pipeline
POST   /api/pipelines/{id}/validate
```

### Providers

```
GET    /api/providers            List configured providers
POST   /api/providers            Add provider
PUT    /api/providers/{id}       Update provider
DELETE /api/providers/{id}
GET    /api/providers/{id}/models List available models
POST   /api/providers/{id}/test  Test connectivity
```

### MCP

```
GET    /api/mcp/servers          List registered MCP servers
POST   /api/mcp/servers          Register MCP server
DELETE /api/mcp/servers/{id}
GET    /api/mcp/servers/{id}/tools  List tools from server
POST   /api/mcp/servers/{id}/call   Direct tool call (debug)
```

### Marketplace & Plugins

```
GET    /api/marketplace/search   Search plugins
GET    /api/marketplace/{id}     Plugin details
POST   /api/plugins/install      Install plugin
GET    /api/plugins              List installed plugins
DELETE /api/plugins/{id}         Uninstall plugin
```

---

## 18. Data Models

### AgentDefinition

```python
class AgentDefinition(SQLModel, table=True):
    id: str
    name: str
    description: str | None
    prompt: PromptConfig
    llm: LLMConfig
    framework: str = "raw"
    skills: list[str] = []
    mcp_servers: list[MCPServerConfig] = []
    plugins: list[str] = []
    collaboration: CollaborationConfig | None
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
```

### Run

```python
class Run(SQLModel, table=True):
    id: str                         # UUID
    agent_id: str | None
    pipeline_id: str | None
    status: RunStatus
    input: RunInput
    output: RunOutput | None
    events: list[HermesEvent] = []  # stored as JSON
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    token_usage: TokenUsage | None
    provider_used: str | None
    error: str | None
```

### HermesEvent

```python
class HermesEvent(BaseModel):
    id: str
    run_id: str
    type: EventType
    agent_id: str | None
    data: dict
    ts: datetime
    sequence: int                   # ordering within a run
```

---

## 19. Phase Roadmap

### Phase 1 — Foundation (Weeks 1–4)

**Goal:** Working agent runner with basic UI and two LLM providers.

- [ ] FastAPI scaffold with SQLite + SQLModel
- [ ] `AgentDefinition` schema (YAML + Pydantic)
- [ ] `AgentFactory` (raw + LangChain adapters)
- [ ] `AgentRunner` (sync + async modes)
- [ ] `EventBus` (in-process asyncio)
- [ ] SSE stream endpoint `/runs/{id}/stream`
- [ ] OpenAI + Ollama providers
- [ ] React + Vite + Tailwind scaffold
- [ ] Basic agent list + run launcher UI
- [ ] Simple node graph (static topology, live status)

### Phase 2 — Multi-LLM + Skills (Weeks 5–8)

- [ ] Anthropic, Gemini, Groq providers
- [ ] Provider fallback chain
- [ ] Skill system (tool skills + prompt skills)
- [ ] 5 built-in skills: web_search, code_exec, file_reader, http_client, formatter
- [ ] Mid-system prompt injection
- [ ] Template variables in prompts
- [ ] Agent builder UI (full prompt editor, skill picker)
- [ ] Run history + event log UI

### Phase 3 — MCP + Framework Adapters (Weeks 9–12)

- [ ] MCP client (SSE + stdio)
- [ ] MCP registry + tool auto-discovery
- [ ] MCP picker in agent builder UI
- [ ] CrewAI adapter
- [ ] AutoGen adapter
- [ ] LlamaIndex adapter
- [ ] Framework selector in UI
- [ ] Redis-backed EventBus (production mode)

### Phase 4 — Pipelines + Multi-Agent (Weeks 13–16)

- [ ] Pipeline YAML schema + DAG executor
- [ ] Fan-out/fan-in execution
- [ ] Pub/sub agent collaboration
- [ ] Supervisor / sub-agent spawning
- [ ] WebSocket endpoint for bidirectional comms
- [ ] Human-in-the-loop pause/resume
- [ ] Visual pipeline designer (drag-and-drop)
- [ ] Animated edge streaming in graph

### Phase 5 — Plugins + Marketplace (Weeks 17–20)

- [ ] Plugin manifest + validation
- [ ] Plugin runtime (sandboxed execution)
- [ ] Plugin types: tool_skill, prompt_skill, framework_adapter
- [ ] Local plugin loader
- [ ] Marketplace registry (self-hosted)
- [ ] Plugin search + install UI
- [ ] Plugin version management

### Phase 6 — Production Hardening (Weeks 21–24)

- [ ] PostgreSQL + Alembic migrations
- [ ] JWT auth + API keys
- [ ] Rate limiting
- [ ] Celery task queue (optional heavy mode)
- [ ] LM Studio + Azure OpenAI + Cohere providers
- [ ] HuggingFace + smolagents + PydanticAI adapters
- [ ] Docker Compose (full stack)
- [ ] Hermes CLI (run, deploy, marketplace commands)
- [ ] Comprehensive test suite
- [ ] AgentCraft native adapter (integrate back into parent)

---

## 20. Integration with AgentCraft

Hermes is designed to be adopted incrementally by AgentCraft:

### Current AgentCraft → Hermes Migration Path

| AgentCraft Component | Hermes Equivalent |
|---|---|
| `core/orchestrator.py` | `hermes/core/runner.py` + `pipeline.py` |
| `core/llm/` (Ollama-only) | `hermes/llm/` (multi-provider) |
| `agents/*/agent.py` | `hermes/agents/*.yaml` + framework adapters |
| `skills/` | `hermes/skills/` (same format, expanded) |
| `comms/` (React UI) | `hermes/studio/` (full Hermes Studio) |
| `frameworks/` | `hermes/frameworks/` (adapter pattern) |

### Hermes as AgentCraft Backend

In a future iteration, AgentCraft's CLI command `python agentcraft bootstrap` will call the Hermes API under the hood, gaining:
- Multi-LLM support (not just Ollama)
- Plugin marketplace for agent capabilities
- Real-time visualization of the agent build workflow
- Pipeline-driven orchestration replacing the custom orchestrator

### `workspace.yaml` Extension

```yaml
# workspace.yaml — extended with hermes
hermes:
  enabled: true
  api_url: http://localhost:8080
  studio_url: http://localhost:3000
  pipeline: agentcraft-build-pipeline
```

---

*Hermes is a sub-project of [AgentCraft](https://github.com/hamzajg/agentcraft). Built to be lightweight, agnostic, and observable — because great agents deserve great infrastructure.*
