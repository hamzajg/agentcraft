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
