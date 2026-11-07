# rfcomm, bnep, and hidp frame probes

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe


def rfcomm_sabm(dlci: int = 0) -> bytes:
    return bytes([0x03, 0x3F, 0x01, 0x1C]) if dlci == 0 else bytes([0x03, (dlci << 2) | 0x03, 0x01, 0x1C])


def rfcomm_uih(dlci: int, payload: bytes) -> bytes:
    return bytes([0x03, (dlci << 2) | 0x03, 0xEF, 0x01]) + payload


def bnep_frame(extension: bool, payload: bytes) -> bytes:
    return bytes([0x80 if extension else 0x00, 0x01]) + payload


def hidp_handshake() -> bytes:
    return bytes([0x00, 0x00, 0x00, 0x00])


@probe("rfcomm_probe", "RFCOMM multiplexer and malformed frames", Level.FUZZ, requires=("classic",), timeout=35)
async def rfcomm_probe(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    cid = await context.transport.connect_psm(0x0003, timeout=5.0)
    if cid is None:
        return ProbeResult("rfcomm_probe", Status.SKIPPED, "RFCOMM PSM not open")
    responses = {}
    for name, frame in {
        "sabm": rfcomm_sabm(0),
        "uih": rfcomm_uih(0, b"\x01\x02\x03"),
        "short": bytes([0x03]),
        "long": bytes([0x03, 0x3F, 0x01, 0x1C]) + b"\xff" * 64,
    }.items():
        responses[name] = (await context.transport.send_l2cap(cid, frame, timeout=1.5) or b"").hex() or None
        await asyncio.sleep(0.1)
    return ProbeResult("rfcomm_probe", Status.OK, f"{sum(v is not None for v in responses.values())}/4 answered", "info", responses)


@probe("bnep_probe", "BNEP setup and malformed frames", Level.FUZZ, requires=("classic",), timeout=35)
async def bnep_probe(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    cid = await context.transport.connect_psm(0x000F, timeout=5.0)
    if cid is None:
        return ProbeResult("bnep_probe", Status.SKIPPED, "BNEP PSM not open")
    responses = {}
    for name, frame in {
        "setup": bytes([0x01, 0x01, 0x02, 0x00]),
        "short": bytes([0x00]),
        "extension": bnep_frame(True, b"\x00" * 8),
        "long": bnep_frame(False, b"\xff" * 64),
    }.items():
        responses[name] = (await context.transport.send_l2cap(cid, frame, timeout=1.5) or b"").hex() or None
        await asyncio.sleep(0.1)
    return ProbeResult("bnep_probe", Status.OK, f"{sum(v is not None for v in responses.values())}/4 answered", "info", responses)


@probe("hidp_probe", "HIDP control channel and handshake", Level.FUZZ, requires=("classic",), timeout=35)
async def hidp_probe(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    cid = await context.transport.connect_psm(0x0011, timeout=5.0)
    if cid is None:
        return ProbeResult("hidp_probe", Status.SKIPPED, "HIDP control PSM not open")
    responses = {}
    for name, frame in {
        "handshake": hidp_handshake(),
        "short": bytes([0x00]),
        "long": bytes([0x00, 0x00, 0x00, 0x00]) + b"\xff" * 64,
    }.items():
        responses[name] = (await context.transport.send_l2cap(cid, frame, timeout=1.5) or b"").hex() or None
        await asyncio.sleep(0.1)
    return ProbeResult("hidp_probe", Status.OK, f"{sum(v is not None for v in responses.values())}/3 answered", "info", responses)
