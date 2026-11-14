# ADR 0001 — Initial architecture

Date: 2026-11-13 (baseline recorded retroactively)
Status: accepted (describes what is built)

## Context

AgentCraft orchestrates a team of local LLM agents that build software from
documentation. It must run fully local (privacy + zero API cost), stay
debuggable, and let humans review before code lands.

## Decisions

1. **Fully local stack: Ollama + Aider.** No cloud LLM APIs. Rationale:
   privacy, offline use, no key management. `diagnose` picks models from
   detected hardware.
2. **Docs-first, human-authored specs.** Agents consume `docs/` written by
   humans; empty docs trigger Phase 0 collaboration rather than codegen.
   Rationale: grounding — agents implement intent, not guesses. This is the
   primary anti-hallucination mechanism.
3. **Self-contained agent folders.** Each agent = `agent.py` + `config.yaml`
   + `prompt.md`; `new-agent` scaffolds. Rationale: agents are drop-in
   composable units; shared logic lives in `core/`, not duplicated.
4. **Checkpointed, resumable workflow.** `bootstrap` auto-resumes from the
   last checkpoint; `resume --from N` / `--phase N` give explicit control.
   Rationale: agent runs are long and flaky; resumability beats restart.
5. **Local RAG over workspace docs.** LanceDB + nomic-embed retrieves
   relevant spec context per task. Rationale: keeps prompts small and
   grounded; runs without external services.
6. **Shared failure taxonomy.** `core/failure.py` classifies step failures
   → retry → escalate to human, used by every agent. Rationale: one place
   for resilience policy (DRY).
7. **Ownership boundary validation.** `agentcraft validate` enforces that
   agents write only inside their declared scope. Rationale: agents writing
   into the platform repo itself would corrupt the tool.
8. **Observer UIs, not orchestrators.** `comms`/`monitor` display state;
   the CLI/orchestrator remains the single source of truth.

## Consequences

- Output quality is bounded by spec quality — the docs-first decision
  trades autonomy for correctness.
- Local models limit capability vs frontier APIs; `diagnose` is the
  mitigation.
- Checkpoint format is internal; changing the workflow phases requires
  migration care.
