# OpenSpec — Agent Instructions

This directory is managed by the OpenSpec framework.

## Structure

```
openspec/
├── specs/                    ← source of truth (current system behaviour)
│   └── <domain>/spec.md
└── changes/                  ← one folder per proposed change
    ├── <change-name>/
    │   ├── proposal.md       ← why + what + scope
    │   ├── specs/<d>/spec.md ← delta specs (ADDED/MODIFIED/REMOVED)
    │   ├── design.md         ← how (technical approach)
    │   └── tasks.md          ← implementation checklist (- [ ] checkboxes)
    └── archive/              ← completed changes
        └── YYYY-MM-DD-<n>/
```

## Workflow

```
proposal.md → specs/ → design.md → tasks.md → implement → archive
```

## Archive a completed change

```bash
make openspec-archive OPENSPEC_CHANGE=<change-name>
```
