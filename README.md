# AgentCraft

An autonomous AI agent team that builds software from documentation. Write your docs, run the agents, review the output, commit.

**Fully local.** Ollama + Aider. No cloud API keys.

---

## Repository layout

```
agentcraft/
│
├── agentcraft            ← single CLI entry point
├── workspace.yaml        ← project config (model, framework, docs path)
├── requirements.txt
│
├── agents/               ← one self-contained folder per agent
│   ├── spec/
│   │   ├── agent.py      agent class + task methods
│   │   ├── config.yaml   skills, personas, framework overrides
│   │   └── prompt.md     system prompt
│   ├── architect/
│   ├── planner/
│   ├── backend_dev/
│   ├── test_dev/
│   ├── reviewer/
│   └── ...               (10 agents total, drop-in extensible)
│
├── core/                 ← runtime infrastructure (not agents)
│   ├── base.py           AiderAgent base class
│   ├── orchestrator.py   agent loop + workflow orchestration
│   ├── framework_loader.py
│   ├── skill_runner.py
│   ├── diagnose.py       hardware detection
│   └── llm/              Ollama client
│
├── rag/                  ← semantic retrieval (LanceDB + nomic-embed)
├── monitor/              ← system metrics collector
├── comms/                ← human↔agent UI (FastAPI + React)
├── skills/               ← global reusable skill library
├── frameworks/           ← methodology bundles (bmad-method, openspec)
│
└── docs/                 ← your project documentation (human-authored)
```

**What agents write** goes to the repo root: `src/`, `api/`, `cli/`, `openspec/`, etc.

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/hamzajg/agentcraft.git
cd agentcraft
pip install -r requirements.txt

# 2. Initialise your project
python agentcraft init

# 3. Detect hardware, select models
python agentcraft diagnose --pull

# 4. Write your docs
mkdir docs
# write docs/blueprint.md, docs/requirements.md, etc.

# 5. Validate workspace and pull models
python agentcraft build

# 6. Run the agents
python agentcraft bootstrap

# 7. Watch the agents work (in a second terminal)
python agentcraft comms          # chat UI → http://localhost:7000
python agentcraft chat architect # or chat with specific agents
python agentcraft monitor        # system metrics
```

---

## The agentcraft CLI

```
python agentcraft <command> [options]
```

| Command | Description |
|---------|-------------|
| `init` | Interactive project setup — creates `workspace.yaml` |
| `diagnose` | Detect CPU/RAM/GPU, select optimal Ollama models |
| `build` | Validate workspace, pull models — no agent execution |
| `bootstrap` | Run the agent workflow (auto-resumes from last checkpoint) |
| `resume --from N` | Resume from a specific iteration |
| `comms` | Start human↔agent chat UI |
| `chat <agent>` | Chat with a specific agent via CLI |
| `monitor` | Live system metrics (CPU, RAM, GPU, agent status) |
| `rag <sub>` | RAG inspector: `stats`, `files`, `queries`, `search`, `reindex` |
| `validate` | Check ownership boundary |
| `frameworks` | List available frameworks |
| `skills` | List available skills |
| `new-agent <n>` | Scaffold a new agent folder |

### Build — Validate & Prepare

No agent execution. Validates the workspace, checks ownership boundaries, and pulls required models.

```bash
python agentcraft build                    # full validation
python agentcraft build --no-validate      # skip ownership check
python agentcraft build --rag              # force-enable RAG
python agentcraft build --framework openspec
```

### Bootstrap — Run the Workflow

Runs the full agent workflow. **Auto-detects** the last completed checkpoint and resumes from there. No need to track where you left off.

```bash
python agentcraft bootstrap                # auto-resume or fresh start
python agentcraft bootstrap --from 5       # force start from iteration 5
python agentcraft bootstrap --phase 2      # only run phase 2
python agentcraft bootstrap --parallel     # run tasks in parallel
```

### Resume — Alias for Bootstrap

Same as `bootstrap` with explicit control over the starting point.

```bash
python agentcraft resume                   # same as bootstrap (auto-detects)
python agentcraft resume --from 8          # start from iteration 8
```

**Empty docs behavior:** If `docs/` is empty, `bootstrap` enters Phase 0 collaboration — the agents work with you to define requirements and generate initial documentation before writing any code.

---

## Workflow

AgentCraft follows an iterative delivery model with immediate feedback:

```
Phase 0 (if docs empty) → Collaboration to define requirements
  ↓
Spec Phase → Generate spec.md + use_cases.md
  ↓
Architecture Planning → LLM plans iterations proportional to complexity
  ↓
For each iteration:
  1. Planner decomposes iteration into tasks
  2. LLM assigns agents to each task
  3. For each task:
     ├─ Agent implements the file
     └─ Immediate review → rework if needed (fast feedback loop)
  4. Integration tests (if LLM decides they're needed)
  5. Holistic reviewer pass
  6. User approval gate
  ↓
Phase complete:
  ├─ Retrospective evaluates what was delivered
  ├─ Plan adapts if needed
  └─ CI/CD infrastructure (if LLM decides it's needed)
```

Key principles:
- **Small iterations** — 1-3 tasks each, proportional to project complexity
- **Immediate feedback** — review after every task, not deferred
- **LLM decides** — whether integration tests, CI/CD, and plan adaptations are needed
- **Walking skeleton first** — get something working end-to-end, then increment

---

## Agents

Each agent is a self-contained folder:

```
agents/backend_dev/
├── agent.py       — BackendDevAgent class with implement() method
├── config.yaml    — skills: [run-checklist, coding-standards]
│                    personas: {bmad-method: developer, openspec: contract-developer}
└── prompt.md      — system prompt injected into every Aider call
```

**Adding an agent:**
```bash
python agentcraft new-agent security_auditor
# Edit agents/security_auditor/prompt.md to define behaviour
```

**Removing an agent:** delete its folder.

---

## Frameworks

Frameworks apply a development methodology to all agents without changing agent code.

```bash
python agentcraft build --framework bmad-method   # user stories, acceptance criteria
python agentcraft build --framework openspec      # spec-driven, proposal → tasks → archive
python agentcraft frameworks                       # list all available
```

Each framework lives in `frameworks/<name>/` with:
- `framework.yaml` — per-agent skill and persona overrides
- `personas/` — role definition overlays (prepended to base prompt)
- `skills/` — framework-specific skills

---

## Skills

Skills are reusable markdown instructions injected as read-only context into every agent call. Declared in `agents/<n>/config.yaml`.

```yaml
# agents/backend_dev/config.yaml
skills:
  - run-checklist      # auto quality gate after every task
  - coding-standards   # project conventions
```

Global skills live in `skills/`. Framework skills live in `frameworks/<fw>/skills/`.

---

## Comms UI

When an agent hits a blocker it sends a message to the comms UI instead of guessing.

```bash
python agentcraft comms          # → http://localhost:7000
python agentcraft comms --dev    # with hot reload
```

Three tabs: **Chat** (agent messages + replies), **Monitor** (live metrics), **RAG** (index observatory).

---

## RAG

```bash
python agentcraft build --rag    # enable semantic context injection
python agentcraft rag stats      # index health
python agentcraft rag files      # per-file breakdown
python agentcraft rag search "session expiry scenario"
```

Requires: `ollama pull nomic-embed-text` (done automatically by `diagnose --pull`).

---

## workspace.yaml

The single file that makes agentcraft aware of your project:

```yaml
project:
  name: my-project
  type: greenfield    # greenfield | legacy | migration
  architecture: monolith   # any style - LLM decides the actual structure

paths:
  docs:   ./docs      # agent team reads these
  output: .           # agents write to repo root

agent_team:
  model:     qwen2.5-coder:7b   # any Ollama model
  framework: null               # bmad-method | openspec | null

rag:
  enabled: false
  embed_model: nomic-embed-text
```

---

## Applying to any project

`agentcraft` is project-agnostic. The agents, frameworks, and skills work on any codebase — CLI tools, web apps, libraries, mobile backends, anything.

```bash
# Copy to your project
cp agentcraft /path/to/your-project/
cp requirements.txt /path/to/your-project/
# Then: python agentcraft init
```
