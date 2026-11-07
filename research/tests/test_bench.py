import pytest

from brunel.bench import Bench, Level
from brunel.mock import MockTransport
from brunel.store import SessionMeta, Store, utc_now


@pytest.mark.asyncio
async def test_mock_bench_finds_route_and_crash(tmp_path):
    transport = MockTransport()
    store = Store(tmp_path, meta=SessionMeta(sessionId="", startedUtc=utc_now(), level="dos"))
    bench = Bench(transport, store, level=Level.DOS, scan_seconds=0.6, settle=0.3, recovery=5)
    results = await bench.run()
    store.close()
    ids = {result.probe for result in results}
    assert "route_read" in ids
    assert "fingerprint" in ids
    assert "eir_overflow" in ids
    assert any(result.status == "crash" for result in results)
    assert any(result.probe == "route_read" and result.finding for result in results)


@pytest.mark.asyncio
async def test_level_filters_fuzz_probes(tmp_path):
    transport = MockTransport()
    store = Store(tmp_path, meta=SessionMeta(sessionId="", startedUtc=utc_now(), level="read"))
    bench = Bench(transport, store, level=Level.READ, scan_seconds=0.5, settle=0.2, recovery=2)
    results = await bench.run()
    store.close()
    assert all(result.probe not in {"att_mtu", "eir_overflow"} for result in results)
