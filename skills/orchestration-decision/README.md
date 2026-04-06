# Orchestration Decision Skill

You are making critical orchestration decisions for the project workflow.

## Your Task

Analyze the current project state and provide a prioritized list of the next N iterations to execute.

## Context You'll Receive

```json
{
  "iterations": [
    {
      "id": 1,
      "phase": 1,
      "name": "Domain Model",
      "agent": "backend_dev",
      "depends_on": [],
      "status": "pending|in_progress|completed|failed"
    }
  ],
  "completed_iterations": [1, 2],
  "current_phase": 1,
  "total_phases": 3
}
```

## Decision Output

Provide a JSON array with decisions in priority order:

```json
[
  {
    "iteration_id": 3,
    "agent": "backend_dev",
    "priority": "high",
    "reason": "Core logic depends on this; no blockers",
    "estimated_time_hours": 2
  },
  {
    "iteration_id": 4,
    "agent": "test_dev",
    "priority": "high",
    "reason": "Can run in parallel with iteration 3",
    "estimated_time_hours": 1.5
  }
]
```

## Key Principles

1. **Dependency Aware**: Only recommend iterations with all dependencies met
2. **Parallelizable**: Identify iterations that can run in parallel
3. **Risk Minimized**: Prioritize work that reduces overall project risk
4. **Feedback Loop**: Consider agent feedback on blockers or issues
5. **Phase Transition**: If phase is complete, recommend phase advancement

## Success Criteria

- Decisions respect iteration dependencies
- Parallelizable work is identified
- Critical path is optimized
- Clear reasoning for each decision
