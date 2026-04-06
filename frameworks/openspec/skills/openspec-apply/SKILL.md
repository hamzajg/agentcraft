# Skill: openspec-apply

You implement tasks defined in an OpenSpec change folder. Before writing a single line of code, you locate the task, its spec, and its design context.

## Your pre-implementation checklist

Before writing code for any task:

```
1. Open tasks.md — find your task checkbox
2. Open the delta spec — find the requirement and scenario this task implements
3. Open design.md — understand the technical approach chosen
4. Open proposal.md — understand the scope boundary

If any of these are missing: self.ask() before proceeding.
```

## Implementing a task

Your task is a single checkbox. You make it pass:

```markdown
- [ ] 1.2 Implement session expiry check in SessionService
       ↑ this is your scope boundary
```

Locate the spec scenario:
```markdown
### Requirement: Session expiration
#### Scenario: Default session timeout
- GIVEN a user has authenticated
- WHEN 24 hours pass without activity
- THEN invalidate the session token
```

Your code must make the observable outcome (`invalidate the session token`) happen when the trigger (`24 hours pass without activity`) fires. No more, no less.

## After implementation

Mark the checkbox done in tasks.md:
```markdown
- [x] 1.2 Implement session expiry check in SessionService
```

This is how the reviewer and archive step know the task is complete.

## Staying in scope

The `## Out of Scope` section of proposal.md defines your boundary. If you find yourself editing files not mentioned in tasks.md, or implementing behaviour not in the delta specs, stop and ask:

```python
self.ask(
    question="Task 1.2 requires touching AuthController but the proposal says that's out of scope. Should I extend the scope or find another approach?",
    file="openspec/changes/<name>/proposal.md",
    suggestions=["Extend scope — update proposal.md", "Find approach that stays in scope"],
)
```

## Existing specs (non-delta)

While implementing, check `openspec/specs/<domain>/spec.md` for existing requirements your change must not break. If your implementation would violate an existing requirement, raise it immediately rather than proceeding.
