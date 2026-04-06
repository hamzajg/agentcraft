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
│   ├── orchestrator.py   agent loop
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

**What agents write** goes to the repo root: `api-gateway/`, `openspec/`, `cli/`, etc.

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
# write docs/blueprint.md, docs/topdown.md, docs/mvp.md

# 5. Build (setup phase)
python agentcraft build

# 6. Bootstrap (execution phase) 
python agentcraft bootstrap

# 7. Watch the agents work (in a second terminal)
python agentcraft comms      # chat UI → http://localhost:7000
python agentcraft chat architect  # or chat with specific agents via CLI
python agentcraft monitor    # system metrics
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
| `build` | Build agents, check violations, setup workspace (fast) |
| `bootstrap` | Run agent workflow, keep alive, print logs (long-running) |
| `resume --from N` | Resume from iteration N after interruption |
| `comms` | Start human↔agent chat UI |
| `chat <agent>` | Chat with a specific agent via CLI |
| `monitor` | Live system metrics (CPU, RAM, GPU, agent status) |
| `rag <sub>` | RAG inspector: `stats`, `files`, `queries`, `search`, `reindex` |
| `validate` | Check ownership boundary |
| `frameworks` | List available frameworks |
| `skills` | List available skills |
| `new-agent <n>` | Scaffold a new agent folder |

```bash
python agentcraft build --help     # full options for any command
python agentcraft build --framework bmad-method
python agentcraft build --framework openspec --rag
python agentcraft build --phase 1 --dry-run
```

**Empty docs behavior:** If `docs/` is empty, `build` performs a "phase 0 bootstrap" that loads all agents and infrastructure, then stops. Use `comms` or `chat <agent>` to collaborate with agents on creating documentation and specifications before starting the full build process.

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

`agentcraft` is project-agnostic. The agents, frameworks, and skills work on any codebase.

```bash
# Copy to your project
cp agentcraft /path/to/your-project/
cp requirements.txt /path/to/your-project/
# Then: python agentcraft init
```
