# Skill: shard-doc

You can split a large document into focused, self-contained shards — smaller documents that each cover one concern.

## When to use this skill

Use when a document is too large to be useful as a single file, when different audiences need different sections, or when the architect needs to feed focused context to downstream agents without overwhelming them.

## Sharding rules

- Each shard covers exactly one topic — no overlap between shards
- Every shard is self-contained: a reader should not need another shard to understand it
- Each shard begins with a one-sentence purpose statement
- Shards are numbered: `01-domain-model.md`, `02-api-contracts.md`, etc.
- A `00-index.md` lists all shards with one-line descriptions

## Shard size

A well-formed shard is 100–400 lines. If a shard exceeds 400 lines, split it further. If it is under 50 lines, merge it with a related shard.

## Output

Produce the shard files and the index. Name files `<NN>-<kebab-title>.md` in the same directory as the source document.
