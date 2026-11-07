import io
import json
import zipfile
from pathlib import Path

import pytest

from brunel import protocol

ASSETS = Path(__file__).resolve().parents[2] / "capture" / "src" / "main" / "assets" / "fieldtest"


def _all_events():
    if not ASSETS.is_dir():
        pytest.skip("field fixtures not present")
    for archive in sorted(ASSETS.glob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if name.endswith("events.jsonl"):
                    for line in io.TextIOWrapper(zf.open(name), encoding="utf-8"):
                        yield json.loads(line)


def _events():
    for event in _all_events():
        if event.get("type") == "advertisement":
            yield event


def test_all_field_advertisements_decode():
    total = 0
    failed = []
    for event in _events():
        total += 1
        raw = bytes.fromhex(event["data"]["bytes"])
        decoded = protocol.decode_bus(protocol.parse_structures(raw))
        if not decoded.ok:
            failed.append((event["data"]["address"], decoded.result))
    assert total > 1000
    assert failed == []


def test_route_text_from_field_log():
    texts = []
    for event in _all_events():
        if event["type"] != "gatt_read":
            continue
        if event["data"].get("characteristic") != protocol.ROUTE_CHARACTERISTIC:
            continue
        parsed = protocol.vehicle_text(bytes.fromhex(event["data"]["bytes"]))
        if parsed:
            texts.append(parsed)
    assert texts
    assert any("Rathausplatz" in text.next_stop for text in texts)
