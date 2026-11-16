# Backlog: agent-capability-manifest

Items are USER STORIES in the parseable format below — keep the heading
shape `## US<n> — <story>` and the field lines intact so `wave_plan` can
parse them. Write the story as: "As a <role>, I want <goal>, so that
<value>" — the title after the dash IS the story.

```
## US<n> — As a <role>, I want <goal>, so that <value>
- Scenarios: @w1, @w2
- Depends: US1, US3        (optional; omit for wave-1 items)
- Size: S|M|L
- Notes: <one line>
```

Order stories by user value; dependencies express technical order only.

## US1 — As a platform integrator, I want a single machine-readable manifest of the agent team, so that I can discover the capability surface without reading source
- Scenarios: @w1
- Size: M
- Notes: core/capabilities.py build_manifest + `agentcraft manifest --format json`.

## US2 — As an agent-team operator, I want each agent's resolved skills with their source and existence, so that I can audit framework shadowing and missing skills before a run
- Scenarios: @w2
- Depends: US1
- Size: M
- Notes: resolution via SkillRunner; source in framework|global|missing.

## US3 — As a human operator, I want a readable summary of the capability surface, so that I can inspect the team at the terminal
- Scenarios: @w3
- Depends: US1
- Size: S
- Notes: `agentcraft manifest --format summary`; update the AGENTS.md/README command table.
