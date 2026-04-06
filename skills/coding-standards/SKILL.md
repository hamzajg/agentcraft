# Skill: coding-standards

These are the project coding standards. Apply them to every file you write.

## Java

- **Spring Boot 3.x** — `jakarta.*` not `javax.*`
- **Reactive** — services return `Mono<T>` or `Flux<T>`; never call `.block()` in production code
- **Immutability** — message model classes are immutable: all fields `final`, set in constructor
- **Sealed classes** — use `sealed` + `permits` for type hierarchies (Java 17+)
- **Records** — use `record` for pure data carriers with no business logic
- **Injection** — constructor injection only; no `@Autowired` on fields
- **Logging** — `private static final Logger log = LoggerFactory.getLogger(ClassName.class)`
- **No magic strings** — extract constants for port numbers, endpoint paths, JSON field names
- **Package structure** — `com.localai.gateway.<layer>.<sublayer>`

## Python

- **Type hints** — all function signatures have type annotations
- **Dataclasses or Pydantic** — no raw dicts for structured data
- **Async** — FastAPI handlers are `async def`; blocking calls use `asyncio.run_in_executor`
- **Logging** — `logger = logging.getLogger(__name__)`
- **No bare except** — always catch specific exception types

## General

- **No dead code** — do not commit commented-out code
- **No TODO comments** — if something is deferred, open a task; do not leave it in the code
- **Error handling** — errors must be handled or explicitly propagated; never silently swallowed
- **Naming** — names describe what, not how; `resolveTeamId` not `doLookup`
