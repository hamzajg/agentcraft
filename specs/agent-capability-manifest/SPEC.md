# Spec: agent-capability-manifest

> Spec-driven development artifact. This file is the contract: implementation
> is done when every acceptance criterion maps to a scenario in
> `EXAMPLES.feature` and every scenario has a passing check.

## Problem

AgentCraft's capability surface — which agents are installed, which framework
and persona each runs under, and which skills each resolves — is only
discoverable by reading source (`agents/*/config.yaml`, `frameworks/*`) or by
running separate commands (`agentcraft skills`, `agentcraft frameworks`) and
knowing an agent name for `agentcraft chat`. There is no single
machine-readable description of the surface for external tooling to consume,
so platform integrators, the comms UI, and CI cannot programmatically answer
"what can this project do?" — which blocks the agentic-ready goal of exposing
an inspectable agent surface.

## Users

- Platform integrator / external orchestrator consuming AgentCraft — needs a
  stable, machine-readable manifest of the capability surface.
- Agent-team operator — needs to audit skill resolution (framework shadowing,
  missing skills) before a run.
- Human operator at the terminal — needs a quick readable inventory.

## Scope (in)

- `core/capabilities.py` with a pure `build_manifest(repo_root, framework_id=None) -> dict`.
- Manifest sections: `schema_version`; `agents` (id, class, framework,
  persona, declared + resolved skills with source/existence); `frameworks`
  (id, label, global skills, overrides); `skills` (available names).
- Fully sorted output, stable across runs.
- CLI `agentcraft manifest` with `--format json|summary` and `--framework`.
- Tests (stdlib-only — no Ollama/aider/RAG imports).

## Scope (out)

- No HTTP/comms endpoint (the CLI is the surface for now).
- No file writes / caching of the manifest.
- No LLM calls or code generation.
- No change to agent behaviour or the orchestrator.

## Acceptance criteria

<!-- Scenario(s): use scenario names verbatim from EXAMPLES.feature and/or
     @w<N> tags — ship_validate resolves both for traceability. -->

| # | Criterion | Scenario(s) |
|---|-----------|-------------|
| 1 | The manifest lists every installed agent with its class name. | @w1 |
| 2 | The manifest carries a schema version and is equal across two builds of the same repo. | @w1 |
| 3 | Each agent entry reports its active framework and persona. | @w1 |
| 4 | Each agent's resolved skills record their source, with framework skills shadowing global ones. | @w2 |
| 5 | A skill named in config but resolvable nowhere is reported as missing, not dropped. | @w2 |
| 6 | The manifest lists available frameworks with their global skills. | @w2 |
| 7 | `--format summary` renders a human-readable inventory. | @w3 |
| 8 | `agentcraft manifest --format json` prints valid JSON to stdout. | @w3 |

## Decisions

- ADR-1: The manifest is derived, read-only state — rebuilt on demand from the
  existing registries (`agents.list_agents`, `FrameworkLoader`, `SkillRunner`);
  no new source of truth is introduced.
- ADR-2: Output ordering is fully sorted (agents, skills, frameworks) so the
  manifest is diffable and cacheable by consumers.
- ADR-3: `schema_version` is an integer, bumped only on breaking shape changes.
