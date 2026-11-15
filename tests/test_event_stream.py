from core.event_stream import FileEventStore


def test_append_and_read_roundtrip(tmp_path):
    store = FileEventStore(tmp_path / "events.jsonl")
    store.append({"type": "build_started", "data": {}, "ts": 1.0})
    store.append({"type": "task_started", "data": {"agent": "dev"}, "ts": 2.0})

    events = store.read_all()

    assert [e["type"] for e in events] == ["build_started", "task_started"]
    assert events[1]["data"]["agent"] == "dev"


def test_tail_returns_last_n(tmp_path):
    store = FileEventStore(tmp_path / "events.jsonl")
    for i in range(10):
        store.append({"type": "tick", "data": {"i": i}, "ts": float(i)})

    tail = store.tail(3)

    assert [e["data"]["i"] for e in tail] == [7, 8, 9]


def test_read_all_missing_file_is_empty(tmp_path):
    store = FileEventStore(tmp_path / "missing.jsonl")
    assert store.read_all() == []


def test_reset_file(tmp_path):
    store = FileEventStore(tmp_path / "events.jsonl")
    store.append({"type": "tick"})

    store.reset_file()

    assert not (tmp_path / "events.jsonl").exists()


# ── reconstruct_state ────────────────────────────────────────────────────────
# Replaying the event log is how both the CLI (`agentcraft build-state`,
# resume detection) and the comms API (`GET /api/build/state`) derive progress.

def _replay(tmp_path, *events):
    store = FileEventStore(tmp_path / "events.jsonl")
    for etype, data, ts in events:
        store.append({"type": etype, "data": data, "ts": ts})
    return store.reconstruct_state()


def test_reconstruct_state_empty_is_idle(tmp_path):
    state = _replay(tmp_path)

    assert state["build_status"] == "idle"
    assert state["completed_iterations"] == []
    assert state["resume_from_iteration"] == 1


def test_reconstruct_state_approved_iteration_sets_resume_point(tmp_path):
    state = _replay(
        tmp_path,
        ("build_started", {}, 1.0),
        ("iter_started", {"id": 1}, 2.0),
        ("iter_done", {"id": 1, "approved": True}, 3.0),
    )

    assert state["build_status"] == "running"
    assert state["completed_iterations"] == [1]
    assert state["approved_count"] == 1
    assert state["current_iter"] is None
    assert state["resume_from_iteration"] == 2
    assert state["last_event_ts"] == 3.0


def test_reconstruct_state_rejected_iteration_does_not_advance_resume(tmp_path):
    state = _replay(
        tmp_path,
        ("build_started", {}, 1.0),
        ("iter_started", {"id": 1}, 2.0),
        ("iter_done", {"id": 1, "approved": False}, 3.0),
    )

    assert state["completed_iterations"] == []
    assert state["rejected_count"] == 1
    assert state["resume_from_iteration"] == 1


def test_reconstruct_state_build_started_resets_progress(tmp_path):
    state = _replay(
        tmp_path,
        ("build_started", {}, 1.0),
        ("iter_done", {"id": 1, "approved": True}, 2.0),
        ("file_written", {"path": "src/Foo.java"}, 3.0),
        ("build_started", {}, 4.0),
    )

    assert state["build_status"] == "running"
    assert state["completed_iterations"] == []
    assert state["approved_count"] == 0
    assert state["delivered_files"] == []
    assert state["resume_from_iteration"] == 1


def test_reconstruct_state_build_done_restarts_from_one(tmp_path):
    state = _replay(
        tmp_path,
        ("build_started", {}, 1.0),
        ("iter_done", {"id": 1, "approved": True}, 2.0),
        ("iter_done", {"id": 2, "approved": True}, 3.0),
        ("build_done", {}, 4.0),
    )

    assert state["build_status"] == "done"
    assert state["completed_iterations"] == [1, 2]
    assert state["current_iter"] is None
    assert state["resume_from_iteration"] == 1


def test_reconstruct_state_paused_then_resumed(tmp_path):
    paused = _replay(tmp_path, ("paused", {}, 1.0))
    assert paused["build_status"] == "paused"

    resumed = _replay(tmp_path, ("paused", {}, 1.0), ("resumed", {}, 2.0))
    assert resumed["build_status"] == "running"


def test_reconstruct_state_records_phases_and_delivered_files(tmp_path):
    state = _replay(
        tmp_path,
        ("build_started", {}, 1.0),
        ("phase_started", {"phase": 1}, 2.0),
        ("phase_done", {"phase": 1}, 3.0),
        ("phase_started", {"phase": 2}, 4.0),
        ("file_written", {"path": "src/A.java"}, 5.0),
        ("file_written", {"path": "src/A.java"}, 6.0),
        ("file_written", {"path": "src/B.java"}, 7.0),
    )

    assert state["phases_completed"] == [1]
    assert state["current_phase"] == 2
    assert state["delivered_files"] == ["src/A.java", "src/B.java"]


# ── sse_events ──────────────────────────────────────────────────────────────

import asyncio
import json

from core.event_stream import sse_events


class _FakeES:
    """Minimal stand-in for _EventStream: recent() + since() over a list."""

    def __init__(self, events):
        self._events = events

    def recent(self, limit=200):
        return self._events[-limit:]

    def since(self, ts):
        return [e for e in self._events if e.get("ts", 0) > ts]


def _ev(i, ts):
    return {"id": f"e{i}", "ts": ts, "type": "tick", "data": {"i": i}}


def _collect(agen, n):
    async def run():
        out = []
        for _ in range(n):
            out.append(await agen.__anext__())
        await agen.aclose()
        return out
    return asyncio.run(run())


def test_sse_events_replays_snapshot_then_streams():
    events = [_ev(i, float(i)) for i in range(1, 6)]
    frames = _collect(
        sse_events(_FakeES(events), snapshot=3, poll_interval=0,
                   heartbeat_interval=0.01),
        4,
    )

    # 3 snapshot frames + 1 live frame (cursor stops advancing after replay,
    # so the live poll re-yields nothing new — next frame is a heartbeat or
    # another snapshot-free poll; assert the first 3 are the tail).
    data_frames = [f for f in frames if f.startswith("id:")]
    assert len(data_frames) >= 3
    ids = [json.loads(f.split("data: ", 1)[1])["id"] for f in data_frames[:3]]
    assert ids == ["e3", "e4", "e5"]


def test_sse_events_since_filters_old_events():
    events = [_ev(i, float(i)) for i in range(1, 6)]
    frames = _collect(
        sse_events(_FakeES(events), since=3.0, poll_interval=0,
                   heartbeat_interval=9999),
        2,
    )
    data_frames = [f for f in frames if f.startswith("id:")]
    ids = [json.loads(f.split("data: ", 1)[1])["id"] for f in data_frames]
    assert ids == ["e4", "e5"]
