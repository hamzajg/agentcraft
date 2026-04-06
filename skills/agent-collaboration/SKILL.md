# Skill: agent-collaboration

You can communicate with other agents in the team using four primitives.
Use them when you need information or help that you cannot get from the docs,
spec, or RAG — meaning you need another agent's expertise or output directly.

## When to use each primitive

### ask_agent — quick expert opinion

Use when you need a fast second opinion before making a decision.
Does not create a task. Does not loop through the orchestrator.

```python
# backend_dev asking reviewer before committing to a design choice
answer = self.ask_agent(
    "reviewer",
    "I'm about to implement AgentMessage as a sealed interface with 5 permits. "
    "Is this the right pattern for a message bus with these variants?",
    context={
        "variants": ["InvokeRequest", "InvokeResponse", "StatusUpdate", "ErrorReport", "Heartbeat"],
        "file": "AgentMessage.java",
    }
)
# answer is a string — use it in your next Aider prompt as additional context
```

```python
# planner asking architect for clarification on scope
answer = self.ask_agent(
    "architect",
    "The spec mentions 'session management' but iteration 2 doesn't include it. "
    "Is that intentional — deferred to phase 2?",
    context={"iteration": 2}
)
```

### share_context / read_context — structured shared knowledge

Use to publish output that other agents will need, or to read what another agent published.
The context store persists for the entire build run.

```python
# spec agent: publish domain model after producing spec.md
self.share_context("domain_model", {
    "entities": ["Agent", "Task", "Iteration", "Message"],
    "invariants": ["Agents communicate only via MessageBus"],
    "patterns": ["actor model", "sealed messages"],
})

# architect agent: publish the full iteration plan
self.share_context("iteration_plan", iterations_list)

# backend_dev reading spec agent's domain model
domain = self.read_context("spec.domain_model")
if domain:
    invariants = domain.get("invariants", [])
    # use invariants to constrain implementation choices
```

Key convention: `"<role>.<topic>"` — e.g. `"spec.domain_model"`, `"architect.iteration_plan"`.
If you omit the role prefix, it is added automatically from your role.

### delegate — assign a subtask to another agent

Use when you need another agent to actually produce a file or artifact.
The delegated agent runs its full task loop. Blocks until complete.

```python
# backend_dev delegates test writing to test_dev for a complex scenario
result = self.delegate(
    "test_dev",
    {
        "id":          "subtask-session-expiry-test",
        "file":        "src/test/java/SessionExpiryTest.java",
        "description": "Write a unit test for session expiry after 24h of inactivity",
        "acceptance_criteria": [
            "Test uses @Test annotation and AssertJ",
            "Test name: sessionExpires_afterInactivity_invalidatesToken",
            "Mock the clock — do not use Thread.sleep",
        ],
    }
)
if result.get("success"):
    # test file was written — proceed with implementation
    pass
```

### broadcast — announce completion or state change

Use when you finish something that other agents might be waiting for,
or when your state changes in a way relevant to the team.

```python
# architect announces that the plan is ready
self.broadcast("plan_ready", {
    "iterations": len(iterations),
    "phases": [1, 2, 3],
    "context_key": "architect.iteration_plan",
})

# backend_dev announces a file is ready for review
self.broadcast("file_ready", {
    "file": "AgentMessage.java",
    "for": "reviewer",
})
```

## Rules

1. **Ask first, implement second** — if you're about to make a non-obvious design decision, ask the architect or reviewer first with `ask_agent`.
2. **Publish what you know** — after producing spec.md, domain_model, iteration_plan, or any structured artifact, publish it with `share_context` so the team has access.
3. **Read before inventing** — before writing code, check `read_context("spec.domain_model")` and `read_context("architect.iteration_plan")` to avoid contradicting the team's agreed design.
4. **Don't over-delegate** — delegation is for subtasks that genuinely need another agent's full expertise. A quick question is `ask_agent`, not `delegate`.
5. **Bus activity is visible** — all messages appear in the comms UI's "Agent Bus" tab. Human reviewers can see all agent-to-agent communication.
