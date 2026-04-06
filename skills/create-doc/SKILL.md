# Skill: create-doc

You produce structured technical documents from specifications, research, or requirements.

## When to use this skill

Use when the task output is a standalone document — a spec, architecture doc, ADR, runbook, or guide — rather than a code file.

## Document structure rules

Every document must have:
1. **Title** — imperative or descriptive, not a question
2. **Purpose** — one sentence: what this document is for
3. **Audience** — who reads this and what they should know before reading
4. **Body sections** — `##` headings, no deeper than `###`
5. **Decisions and rationale** — for architecture/ADR docs, every decision has a "why" paragraph

## Writing rules

- Sentence case for all headings
- Code examples for all technical claims — never describe code in prose without showing it
- Tables for comparisons — never compare in prose when a table is clearer
- No filler: "This document aims to..." → delete and start with the content
- Active voice: "The gateway resolves agents" not "Agents are resolved by the gateway"

## Template

If a `template.md` file exists in this skill's folder, use it as the structural starting point for the document.
