# Skill: openspec-review

You understand the OpenSpec change lifecycle and can verify a change is complete, spec-compliant, and ready to archive.

## The change lifecycle

```
propose → specs → design → tasks → implement → review → archive
```

Archive merges delta specs into `openspec/specs/<domain>/spec.md` and moves the change folder to `openspec/changes/archive/YYYY-MM-DD-<name>/`.

## Reviewing a change

### Step 1 — Completeness check

```
openspec/changes/<n>/
  proposal.md     ← exists? has Why / What Changes / Impact / Out of Scope?
  specs/<d>/spec.md ← exists? has ADDED/MODIFIED/REMOVED markers?
  design.md       ← exists? references proposal?
  tasks.md        ← exists? all boxes checked (- [x])?
```

If anything is missing or malformed: `INCOMPLETE: <file> — <what is missing>`

### Step 2 — Spec compliance

For each requirement in the delta specs:

```
ADDED Requirement: Session expiration
  → Is there a test named for the scenario? (sessionExpiresAfterConfiguredDuration)
  → Does the test verify the observable outcome (session invalidated)?
  → Does the implementation make the test pass?
```

If any requirement has no test: `SPEC VIOLATION: no test for scenario "<n>"`
If any implementation has no requirement: `SCOPE VIOLATION: <code> implements behaviour not in specs`

### Step 3 — Archive readiness

When all checks pass:
```
APPROVED FOR ARCHIVE
Change: <name>
Specs to merge: openspec/changes/<n>/specs/ → openspec/specs/
Archive path: openspec/changes/archive/YYYY-MM-DD-<name>/
```

## The archive merge

When a change is archived, its delta specs are merged into the main specs:
- `## ADDED Requirements` sections are appended to the domain spec
- `## MODIFIED Requirements` changes replace the old text
- `## REMOVED Requirements` items are deleted from the domain spec

The result is `openspec/specs/<domain>/spec.md` growing to reflect the current state of the system.

## Reading existing specs

`openspec/specs/` is the source of truth for what the system currently does. Before reviewing a change, scan the relevant domain spec to understand what requirements already exist. The change must not silently break existing requirements.
