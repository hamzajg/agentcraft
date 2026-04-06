# Skill: create-story

You can produce structured user stories from feature descriptions or requirements.

## When to use this skill

Use when decomposing a feature or iteration goal into user-facing stories that clearly express who needs what and why.

## Story format

```
## Story: <short imperative title>

**As a** <actor>
**I want** <capability>
**So that** <benefit>

### Acceptance criteria
- Given <precondition>, when <action>, then <observable outcome>
- Given ..., when ..., then ...

### Notes
- <constraints, edge cases, out of scope>
```

## Rules

- The actor is a real user type — not "the system" or "the developer"
- The benefit must state business or user value — not technical implementation
- Each acceptance criterion must be independently verifiable
- Write at least 2 acceptance criteria per story
- Mark out-of-scope items explicitly — this prevents scope creep

## Story sizing

A well-formed story fits in one iteration. If the story requires more than 5 acceptance criteria, split it into two stories.
