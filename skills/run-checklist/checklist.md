# Project Checklist

This file is the project-specific checklist. It overrides the universal checklist in SKILL.md when present.

## Java files
- [ ] Uses `jakarta.*` not `javax.*` (Spring Boot 3)
- [ ] Services return `Mono<T>` or `Flux<T>` — no blocking calls
- [ ] Sealed classes have correct `permits` clause
- [ ] `LoggerFactory.getLogger(ClassName.class)` — not `System.out.println`
- [ ] No `@Autowired` on fields — use constructor injection
- [ ] Records used for immutable data carriers

## Test files
- [ ] One `@Test` per behaviour
- [ ] `assertThat` from AssertJ — not JUnit assertions
- [ ] Reactive: `StepVerifier.create(...)` — not `.block()`
- [ ] No `@Disabled` tests
- [ ] No empty test bodies

## JSON registry files
- [ ] Valid JSON (no trailing commas, no comments)
- [ ] Field names match Java model exactly (`studioTeam`, not `studio_team`)
- [ ] All required fields present

## Shell scripts
- [ ] `#!/bin/bash` shebang
- [ ] `set -e` or explicit error handling
- [ ] Variables quoted: `"$VAR"` not `$VAR`
