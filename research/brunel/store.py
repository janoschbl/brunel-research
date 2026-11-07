# append-only jsonl evidence store, same schema as the capture app

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class SessionMeta:
    sessionId: str
    startedUtc: str
    state: str = "running"
    appVersion: str = "brunel-bench/1"
    device: str = ""
    scan: str = ""
    bench: bool = True
    level: str = "read"
    targets: list[str] = field(default_factory=list)
    stoppedUtc: str | None = None
    events: int = 0
    advertisements: int = 0
    dropped: int = 0
    bytes: int = 0
    eventsSha256: str | None = None
    notes: list[str] = field(default_factory=list)


class Store:
    def __init__(self, root: Path, session_id: str | None = None, meta: SessionMeta | None = None):
        self.root = Path(root)
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self.dir = self.root / self.session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta = meta or SessionMeta(session_id=self.session_id, startedUtc=utc_now())
        self.meta.sessionId = self.session_id
        self._lock = threading.Lock()
        self._seq = 0
        self._events = 0
        self._ads = 0
        self._dropped = 0
        self._fh = (self.dir / "events.jsonl").open("a", encoding="utf-8")
        self._write_meta()

    def _write_meta(self) -> None:
        (self.dir / "session.json").write_text(json.dumps(asdict(self.meta), ensure_ascii=False, indent=2))

    def event(self, event_type: str, data: dict[str, Any] | None = None, profile_id: str | None = None, operation_id: str | None = None) -> None:
        with self._lock:
            self._seq += 1
            self._events += 1
            if event_type == "advertisement":
                self._ads += 1
            record = {
                "schemaVersion": SCHEMA_VERSION,
                "sessionId": self.session_id,
                "sequence": self._seq,
                "eventId": f"{self.session_id}-{self._seq}",
                "type": event_type,
                "timestampUtc": utc_now(),
                "elapsedRealtimeNanos": time.monotonic_ns(),
                "profileId": profile_id,
                "operationId": operation_id,
                "data": data or {},
            }
            self._fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._fh.flush()

    def advertisement(self, profile_id: str, data: dict[str, Any]) -> None:
        self.event("advertisement", data, profile_id=profile_id)

    def note(self, text: str, profile_id: str | None = None) -> None:
        self.meta.notes.append(text)
        self.event("note", {"text": text}, profile_id=profile_id)

    def close(self, state: str = "completed") -> None:
        with self._lock:
            self.meta.state = state
            self.meta.stoppedUtc = utc_now()
            self.meta.events = self._events
            self.meta.advertisements = self._ads
            self.meta.dropped = self._dropped
            self.meta.bytes = (self.dir / "events.jsonl").stat().st_size
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()
            self._write_meta()
            self.meta.eventsSha256 = _sha256_file(self.dir / "events.jsonl")
            self._write_meta()

    def profiles(self, profiles: list[dict[str, Any]]) -> None:
        (self.dir / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2))

    def bench_summary(self, summary: dict[str, Any]) -> None:
        (self.dir / "bench.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close("incomplete" if exc[0] else "completed")


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_events(path: Path) -> list[dict[str, Any]]:
    events = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def load_session(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = Path(path)
    meta = json.loads((path / "session.json").read_text())
    return meta, read_events(path / "events.jsonl")
