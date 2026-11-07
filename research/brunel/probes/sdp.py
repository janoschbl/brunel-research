# sdp enumeration and parser probes

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe


@probe("sdp_browse", "Browse the SDP server and list service records", Level.READ, requires=("classic",), timeout=45)
async def sdp_browse(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    records = await context.transport.sdp_search()
    if not records:
        return ProbeResult("sdp_browse", Status.OK, "no service records", "info")
    return ProbeResult(
        "sdp_browse",
        Status.FINDING,
        f"{len(records)} service records",
        "info",
        {"records": records},
    )


@probe("sdp_fuzz", "Malformed SDP PDUs", Level.FUZZ, requires=("classic",), timeout=45)
async def sdp_fuzz(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    cases = {
        "search": protocol.sdp_service_search(),
        "attribute": protocol.sdp_service_attribute(0x00010000),
        "search-attribute": protocol.sdp_service_search_attribute(),
        "empty-search": protocol.sdp_pdu(0x02, 4, b"\x00\x00"),
        "bad-pdu": protocol.sdp_pdu(0x7F, 5),
        "truncated": protocol.sdp_pdu(0x02, 6, b"\x00"),
        "huge-max": protocol.sdp_pdu(0x02, 7, b"\xff\xff\x35\x03\x19\x11\x0b"),
        "bad-continuation": protocol.sdp_pdu(0x04, 8, b"\x00\x01\x00\x00\x00\x01\xff\x35\x05\x0a\x00\x00\xff\xff"),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.sdp_raw(pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.15)
    return ProbeResult("sdp_fuzz", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)
