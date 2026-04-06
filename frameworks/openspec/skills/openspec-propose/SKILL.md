# Skill: openspec-propose

You know how to create a complete OpenSpec change proposal — a self-contained folder with everything needed to implement and review a change.

## The change folder structure

```
openspec/changes/<change-name>/
├── proposal.md           ← why + what + impact
├── specs/                ← delta specs (requirement changes only)
│   └── <domain>/
│       └── spec.md
├── design.md             ← how (technical approach)
└── tasks.md              ← implementation checklist (- [ ] checkboxes)
```

## Artifact order and dependencies

Artifacts build on each other and must be created in order:

```
proposal.md  →  specs/  →  design.md  →  tasks.md  →  implement
    why           what         how          steps
```

You cannot write design.md without proposal.md existing.
You cannot write tasks.md without design.md existing.

## proposal.md template

```markdown
# Proposal: <change-name>

## Why
One paragraph. The problem being solved or the capability being added.
Be specific — "users requested" is not specific. "Users cannot log out on mobile" is.

## What Changes
Bullet list of capabilities:
- ADD: <new behaviour>
- MODIFY: <existing behaviour that changes>
- REMOVE: <behaviour being dropped>

## Impact
- Specs affected: openspec/specs/<domain>/spec.md
- Components affected: <list>
- Breaking changes: yes/no — if yes, what

## Out of Scope
What this change explicitly does NOT include.
```

## Delta spec format

Specs describe behaviour, not implementation. Use SHALL / SHALL NOT language.
Use markers so the archive step can merge cleanly:

```markdown
# Delta for <domain>

## ADDED Requirements
### Requirement: <name>
The system SHALL <observable behaviour>.

#### Scenario: <name>
- GIVEN <precondition>
- WHEN <action or event>
- THEN <observable outcome>
- AND <additional observable outcome>

## MODIFIED Requirements
### Requirement: <existing name>
- The system SHALL expire sessions after 24 hours.
+ The system SHALL support configurable session expiration.

## REMOVED Requirements
### Requirement: <name>
Removed because: <reason>.
```

## tasks.md format

```markdown
# Tasks: <change-name>

## <Feature or phase name>

- [ ] 1.1 <test task — write failing test for scenario X>
- [ ] 1.2 <implementation task — make 1.1 pass>
- [ ] 2.1 <test task>
- [ ] 2.2 <implementation task>
```

Rules:
- Every checkbox uses `- [ ]` format (required for task tracking)
- Test task before implementation task, always
- One checkbox = one clear action (one file, one function, one config change)
- Reference the spec scenario: `(spec: Session expiration → Default session timeout)`
