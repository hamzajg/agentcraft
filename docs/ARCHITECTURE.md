# Architecture — agentcraft

Current-state map. Descriptive, not aspirational; see `docs/adr/` for why.

## System shape

```
human docs/ (blueprint, requirements, …)
        │
        ▼
python agentcraft <cmd>          ← agentcraft (CLI entry)
        │
        ├─ init / diagnose / build   workspace setup, hardware→model pick, validation
        ├─ bootstrap / resume        orchestrated agent workflow (checkpointed)
        ├─ comms / chat / monitor    human↔agent interfaces
        └─ rag / validate / skills / frameworks / new-agent
        │
        ▼
core/  orchestrator + AiderAgent base + Ollama client + failure taxonomy
        │
        ├─ agents/<name>/   spec → architect → planner → backend_dev → test_dev → reviewer …
        │                    each: agent.py + config.yaml + prompt.md
        ├─ rag/             LanceDB retrieval over workspace docs (context grounding)
        ├─ monitor/         hardware/agent metrics
        └─ comms/           FastAPI + React chat UI (:7000)
        │
        ▼
Ollama (local models) + Aider  →  writes generated code into the WORKSPACE repo
```

## Layers and rules

- **CLI layer** (`agentcraft` file): argument parsing and dispatch only.
- **Core runtime** (`core/`): orchestration, agent base class, LLM client,
  failure classification, file helpers. Shared by all agents — agents must
  not reimplement this.
- **Agent layer** (`agents/`): self-contained per-agent folders. An agent
  declares skills/personas/framework overrides in `config.yaml` and its
  system prompt in `prompt.md`.
- **Knowledge layer** (`rag/`): LanceDB + nomic-embed embeddings over the
  workspace docs; gives agents grounded context instead of hallucinating.
- **Interface layer** (`comms/`, `monitor/`): human visibility — chat,
  metrics. Observer role, not part of the agent loop.

## State

- `workspace.yaml` — project config (model, framework, docs path) created
  by `init`.
- Checkpoints — `bootstrap`/`resume` persist progress so runs are
  resumable and idempotent-ish across interruptions.
- LanceDB index under the workspace — rebuildable via `agentcraft rag reindex`.
- Agents' output lands in the consuming project root (`src/`, `api/`, …),
  keeping this repo clean.

## Workflow model

Phased, checkpointed agent pipeline: spec → architecture → planning →
implementation (backend/frontend as configured) → tests → review. With
empty docs, Phase 0 is a collaboration mode where agents help author the
docs first — code generation never starts without human-authored specs.
