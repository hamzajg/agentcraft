# AGENTS.md — agentcraft

Guidance for AI agents (and humans) working in this repository.

## Project

AgentCraft is an autonomous AI agent team that builds software from
human-authored documentation. Agents (spec, architect, planner, backend_dev,
test_dev, reviewer, …) run locally via Ollama + Aider — no cloud API keys.
This repo IS the agent platform itself: a CLI (`agentcraft`), agent
definitions, runtime core, RAG, monitor, and a comms UI.
Stack: Python 3.13, Ollama, Aider, LanceDB (RAG), FastAPI + React (comms).

## Commands

Verified 2026-11-13 against CI (`.github/workflows/ci.yml`).

| Task | Command |
|---|---|
| Install deps | `pip install -r requirements.txt` (dev: `requirements-dev.txt`) |
| CLI entry | `python agentcraft <command>` (Makefile aliases exist) |
| Smoke test | `python agentcraft --help` |
| Test | `pytest` (`pytest.ini`: `testpaths=tests`, `pythonpath=.`) |
| Project setup | `python agentcraft init` → writes `workspace.yaml` |
| Hardware check | `python agentcraft diagnose --pull` |
| Validate workspace | `python agentcraft build` |
| Run agents | `python agentcraft bootstrap` (auto-resumes checkpoints) |
| Chat UI | `python agentcraft comms` → http://localhost:7000 |

Requires: Ollama installed with models pulled (`diagnose --pull`), a
`workspace.yaml` from `init`, and human-authored docs in the workspace's
`docs/` dir.

## Architecture

- `agentcraft` — single CLI entry point dispatching to subcommands.
- `agents/<name>/` — one self-contained folder per agent: `agent.py`,
  `config.yaml` (skills/personas/framework overrides), `prompt.md`.
  Drop-in extensible; `agentcraft new-agent <name>` scaffolds one.
- `core/` — runtime infra, NOT agents: `base.py` (AiderAgent base),
  `orchestrator.py` (agent loop + workflow), `framework_loader.py`,
  `skill_runner.py`, `diagnose.py` (hardware→model selection),
  `failure.py` (shared classify→retry→ask taxonomy), `files.py`, `llm/`
  (Ollama client).
- `rag/` — LanceDB + nomic-embed semantic retrieval over workspace docs.
- `monitor/` — system metrics collector.
- `comms/` — FastAPI + React human↔agent chat UI.
- `skills/` — global reusable skill library; `frameworks/` — methodology
  bundles (bmad-method, openspec); `prompts/` — shared prompt fragments.
- `openspec/` — spec-driven change proposals (agent-readable markdown).

Agents write generated code to the consuming project's root (`src/`,
`api/`, …) — never into `agentcraft/` internals.

## Conventions

- Agent = folder with `agent.py` + `config.yaml` + `prompt.md`. Keep agents
  self-contained; shared behavior goes in `core/` or `skills/`, not copied
  per-agent (DRY).
- Specs/prompts/context are Markdown; executable logic is Python (the
  harness-wide D002 boundary applies here too).
- Failure handling goes through `core/failure.py` taxonomy — don't invent
  per-agent retry logic.
- KISS: no frameworks beyond the listed stack; `pythonpath=.` means tests
  import from repo root.

## Landmines

- `bootstrap` **auto-resumes from the last checkpoint** — it is not a fresh
  run by default; use `--from N` / `--phase N` to control it.
- Empty `docs/` → Phase 0 collaboration mode, not an error.
- Ownership boundary is enforced (`agentcraft validate`) — agents must not
  write outside their declared scope.
- RAG is local (LanceDB) — first `rag` commands may build the index
  (`rag reindex`).
- `docs/` in a *workspace* is human-authored input; this repo's own
  `docs/` holds repo documentation — don't confuse the two when editing.

## Agent rules

- Branch from `main`; name branches `feat/*`, `fix/*`, `chore/*`, `docs/*`.
- Docs-only changes still go through a PR; never commit to `main` directly.
- Verify before claiming: run `pytest` (and `python agentcraft --help` for
  CLI changes) and report the real result.
- Keep changes minimal and consistent with surrounding code. No drive-by
  refactors.
- Update AGENTS.md / docs/ARCHITECTURE.md when your change alters commands,
  the agent folder contract, or module layout.
