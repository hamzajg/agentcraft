# Skill: bmad-story (BMAD Method)

This skill extends the base create-story skill with BMAD-specific practices.

## BMAD story additions

Every story must include:

### Ubiquitous language
Define domain terms that must appear verbatim in code:
```
## Ubiquitous language
- Agent: an AI role with a specific capability, identified by ID
- Task: a multi-step work item requiring multiple agents
- Clarification: a question an agent raises that requires human input
```

### Definition of done
```
## Definition of done
- [ ] Acceptance criteria covered by passing tests
- [ ] Ubiquitous language terms used in class/method names
- [ ] No hardcoded values
- [ ] Reviewed and APPROVED by reviewer agent
```

### Story dependencies
```
## Depends on
- UC-1 (agent registry must exist before agent resolution)
```
