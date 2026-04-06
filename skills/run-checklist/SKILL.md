# Skill: run-checklist

You have the ability to run a structured checklist against any file or output you produce.

## When to use this skill

Run the checklist automatically after completing your primary task, before considering the task done. Think of it as your own quality gate.

## How to use this skill

After completing your output, mentally walk through the checklist below. For each item that fails, revise your output before finalising it. Do not report the checklist results — just act on failures silently.

If the checklist is provided as a separate file (`checklist.md`), use that. Otherwise use the universal checklist below.

## Universal checklist

### Completeness
- [ ] Every requirement in the task description is addressed
- [ ] Every acceptance criterion is satisfied
- [ ] No placeholder TODOs remain in the output
- [ ] No "..." or truncated content

### Correctness
- [ ] All referenced types, interfaces, and field names exist
- [ ] All imports are present and correct
- [ ] No method stubs (`throw new UnsupportedOperationException()`)
- [ ] Return types match what callers expect

### Consistency
- [ ] Naming conventions match the existing codebase
- [ ] Package structure follows the project conventions
- [ ] Field names match the JSON/YAML schema exactly

### Quality
- [ ] No dead code or unused variables
- [ ] Error cases are handled, not silently swallowed
- [ ] Logging follows the project pattern

## Reporting failures

If after revision the checklist still has failures you cannot resolve, call `self.ask()` with the specific blocker rather than producing incomplete output.
