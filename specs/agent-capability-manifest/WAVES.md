# Waves — agent-capability-manifest

Each wave IS an iteration: a time-boxed, independently shippable
increment — one branch, one PR, green tests, demoable outcome.
Do not start wave N+1 until wave N merges.

## Wave 1 — iteration 1

Scenarios proven by this wave:
- manifest lists every installed agent with its class
- manifest is deterministic and carries a schema version
- each agent reports its active framework and persona

| Item | Title | Size | Deps | Notes |
|------|-------|------|------|-------|
| US1 | As a platform integrator, I want a single machine-readable manifest of the agent team, so that I can discover the capability surface without reading source | M | — | core/capabilities.py build_manifest + `agentcraft manifest --format json`. |

## Wave 2 — iteration 2

Scenarios proven by this wave:
- resolved skill records its source and framework shadows global
- a missing skill is reported rather than dropped
- manifest lists frameworks with their global skills

| Item | Title | Size | Deps | Notes |
|------|-------|------|------|-------|
| US2 | As an agent-team operator, I want each agent's resolved skills with their source and existence, so that I can audit framework shadowing and missing skills before a run | M | US1 | resolution via SkillRunner; source in framework|global|missing. |

## Wave 3 — iteration 3

Scenarios proven by this wave:
- summary format renders a human-readable inventory
- manifest command emits valid JSON to stdout

| Item | Title | Size | Deps | Notes |
|------|-------|------|------|-------|
| US3 | As a human operator, I want a readable summary of the capability surface, so that I can inspect the team at the terminal | S | US1 | `agentcraft manifest --format summary`; update the AGENTS.md/README command table. |
