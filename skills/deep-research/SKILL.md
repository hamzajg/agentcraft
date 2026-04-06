# Skill: deep-research

You can produce a structured research brief on any technical topic relevant to the task at hand.

## When to use this skill

Use when the task requires knowledge that may be ambiguous, contested, or where multiple valid approaches exist. Research before specifying — never assume one approach when the spec should present options.

## Research output format

```
## Research: <topic>

### Summary
One paragraph — the essential answer.

### Options considered
| Option | Pros | Cons | Best for |
|--------|------|------|---------|
| ...    | ...  | ...  | ...     |

### Recommendation
Which option fits this project and why.

### Sources / references
- <concept or pattern name>: <brief description>
```

## Rules

- Present at least 2 options for any non-trivial decision
- Do not recommend an option without explaining why it fits THIS project
- Flag assumptions explicitly: "This recommendation assumes X"
- Keep the summary actionable — the reader should be able to act on it without reading the full brief
