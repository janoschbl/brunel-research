import json

from brunel.store import SessionMeta, Store, load_session, utc_now


def test_store_writes_schema_and_hashes(tmp_path):
    store = Store(tmp_path, meta=SessionMeta(sessionId="", startedUtc=utc_now()))
    store.event("probe_result", {"probe": "x", "status": "ok"})
    store.advertisement("p-1", {"address": "AA"})
    store.close()
    meta, events = load_session(store.dir)
    assert meta["state"] == "completed"
    assert meta["eventsSha256"]
    assert [event["type"] for event in events] == ["probe_result", "advertisement"]
    assert events[0]["sequence"] == 1
    assert events[0]["eventId"].endswith("-1")
    assert json.loads((store.dir / "session.json").read_text())["events"] == 2
