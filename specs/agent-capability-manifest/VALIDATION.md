# Validation — agent-capability-manifest

## Traceability

| AC | Criterion | Scenarios | Wave(s) | Test evidence |
|----|-----------|-----------|---------|---------------|
| 1 | The manifest lists every installed agent with its class… | each agent reports its active framework and persona, manifest is deterministic and carries a schema version, manifest lists every installed agent with its class | 1 | (weak) test_capabilities.py |
| 2 | The manifest carries a schema version and is equal across… | each agent reports its active framework and persona, manifest is deterministic and carries a schema version, manifest lists every installed agent with its class | 1 | (weak) test_capabilities.py |
| 3 | Each agent entry reports its active framework and persona. | each agent reports its active framework and persona, manifest is deterministic and carries a schema version, manifest lists every installed agent with its class | 1 | (weak) test_capabilities.py |
| 4 | Each agent's resolved skills record their source, with… | a missing skill is reported rather than dropped, manifest lists frameworks with their global skills, resolved skill records its source and framework shadows global | 2 | (weak) test_capabilities.py |
| 5 | A skill named in config but resolvable nowhere is reported… | a missing skill is reported rather than dropped, manifest lists frameworks with their global skills, resolved skill records its source and framework shadows global | 2 | (weak) test_capabilities.py |
| 6 | The manifest lists available frameworks with their global… | a missing skill is reported rather than dropped, manifest lists frameworks with their global skills, resolved skill records its source and framework shadows global | 2 | (weak) test_capabilities.py |
| 7 | `--format summary` renders a human-readable inventory. | manifest command emits valid JSON to stdout, summary format renders a human-readable inventory | 3 | (weak) test_capabilities.py |
| 8 | `agentcraft manifest --format json` prints valid JSON to… | manifest command emits valid JSON to stdout, summary format renders a human-readable inventory | 3 | (weak) test_capabilities.py |

## Scenario coverage

- Scenarios: 8 total, 0 with detected test evidence, 8 with weak (token-match) evidence only, 0 without
- ~ `manifest lists every installed agent with its class` (@w1)
- ~ `manifest is deterministic and carries a schema version` (@w1)
- ~ `each agent reports its active framework and persona` (@w1)
- ~ `resolved skill records its source and framework shadows global` (@w2)
- ~ `a missing skill is reported rather than dropped` (@w2)
- ~ `manifest lists frameworks with their global skills` (@w2)
- ~ `summary format renders a human-readable inventory` (@w3)
- ~ `manifest command emits valid JSON to stdout` (@w3)

## Demo script (manual walkthrough)

1. **manifest lists every installed agent with its class** — run the app, perform the scenario, observe the outcome.

## Gaps

- none — spec is fully traced

Note: 'no evidence' means neither the scenario name nor a
token match was found in test files — verify by hand before
treating it as a real gap. '~' marks weak token-match evidence.