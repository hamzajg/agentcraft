# ADR 0002 — SSE event stream for remote agent clients

## Status

Accepted — implemented on `feat/live-event-stream`.

## Context

The queued candidate was a "remote agent API — REST/SSE surface over the
existing event store + build-state". Inspection showed most of it already
exists: `comms/main.py` already serves `/api/live/events`,
`/api/build/state`, `/api/control/state`, `/api/bus/*`, and
`/api/workspace/*` as plain REST, and `/api/metrics` already streams via
SSE. The one real gap: live build events were only consumable over the
browser WebSocket `/ws` — non-browser agent clients (scripts, other
agent CLIs, curl) had to poll `/api/live/events`.

## Decision

- `core/event_stream.py::sse_events(es, since, snapshot, …)` — a
  framework-free async generator that tails `ES` (file store first, ring
  buffer fallback) and yields SSE frames (`id:` + `data:` JSON) with
  heartbeat comments. `since <= 0` replays the last `snapshot` events
  for catch-up, then streams live; `since > 0` resumes strictly after
  that timestamp.
- `comms/main.py` — `GET /api/live/stream?since=&snapshot=` wraps it in
  `StreamingResponse` (`text/event-stream`), same headers as
  `/api/metrics`.
- Read-only by construction: the endpoint exposes the same event log the
  UI already sees; control stays on the existing `/api/control/*` verbs.

## Consequences

- Any HTTP client can now tail build progress without a WebSocket
  client; `Last-Event-ID`-style resume works via the `id:`/`since`
  cursor (the file store's `ts` is the resume key — event `id`s are
  short uuids, not ordered).
- Polling cost is one `FileEventStore.read_all()`/`tail()` per second —
  acceptable at this repo's event volume; if it grows, the store needs
  an offset/seek API (deferred).
- No auth was added: comms is a localhost dev UI with no auth model;
  exposing this endpoint does not widen the trust boundary. If comms is
  ever bound beyond localhost, auth is a prerequisite for the whole API.
