# Universal Agent Rules

These rules apply to ALL agents. Follow them strictly.

## Output Rules

1. **Output ONLY the requested content** — no explanation, no preamble, no sign-off
2. **NEVER use placeholders, stubs, or TODO comments** — write complete, working content
3. **NEVER say "rest of file here" or "implement the remaining parts"** — output everything
4. **If writing code**: output the full file with all imports, definitions, and entry points
5. **If writing docs**: output the complete document with all sections filled in
6. **If the file already exists**: replace only the relevant sections, keep the rest intact

## Anti Over-Engineering

1. Implement ONLY what was explicitly requested
2. Do NOT add features, frameworks, or "good practices" that weren't asked for
3. Keep complexity proportional to the request
4. When in doubt, choose the simpler option
5. If the request is ambiguous, ask for clarification rather than assuming

## File Writing

1. Output the COMPLETE file content — nothing partial
2. The file must be valid and runnable as-is (for code)
3. Use idiomatic patterns for the language/format
4. Handle errors gracefully (for code)
5. No markdown code fences in the output — write raw file content
