# l2cap signaling probes for the kernel and bluez

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe


async def _classic(context: Context) -> None:
    await context.connect(classic=True)


@probe("l2cap_info", "L2CAP information requests", Level.READ, requires=("classic",), timeout=25)
async def l2cap_info(context: Context) -> ProbeResult:
    await _classic(context)
    responses = {}
    for info_type in (0x0001, 0x0002, 0x0003, 0x0004, 0xFFFF):
        response = await context.transport.send_l2cap(1, protocol.l2cap_info_request(1, info_type), timeout=2.0)
        responses[f"0x{info_type:04x}"] = response.hex() if response else None
    return ProbeResult("l2cap_info", Status.OK, f"{sum(v is not None for v in responses.values())}/5 answered", "info", responses)


@probe("l2cap_connect", "L2CAP connect to common PSMs", Level.READ, requires=("classic",), timeout=40)
async def l2cap_connect(context: Context) -> ProbeResult:
    await _classic(context)
    accepted = {}
    for psm, label in protocol.KNOWN_PSMS.items():
        response = await context.transport.send_l2cap(1, protocol.l2cap_connect(2, psm), timeout=1.5)
        if response and response[0] == 0x03 and len(response) >= 12:
            result = int.from_bytes(response[8:10], "little")
            if result == 0:
                accepted[label] = psm
    return ProbeResult(
        "l2cap_connect",
        Status.FINDING if accepted else Status.OK,
        "accepted: " + ", ".join(accepted) if accepted else "no PSM accepted",
        "info",
        {"accepted": accepted},
    )


@probe("l2cap_ecrb", "Enhanced Credit Based connection request", Level.FUZZ, requires=("classic",), timeout=25)
async def l2cap_ecrb(context: Context) -> ProbeResult:
    await _classic(context)
    cases = {
        "normal": protocol.l2cap_ecrb(3, 0xFFFF, 0xFFFF, 0xFFFF),
        "zero": protocol.l2cap_ecrb(4, 0, 0, 0),
        "small": protocol.l2cap_ecrb(5, 23, 23, 1),
        "truncated": protocol.l2cap_command(0x0C, 6, b"\x01"),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_l2cap(1, pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("l2cap_ecrb", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("l2cap_credit", "LE Credit Based connection request", Level.FUZZ, requires=("classic",), timeout=25)
async def l2cap_credit(context: Context) -> ProbeResult:
    await _classic(context)
    cases = {
        "normal": protocol.l2cap_credit_based_connect(7, 0x0080, 0x0040, 0x0200, 0x0100, 0x0010),
        "zero": protocol.l2cap_credit_based_connect(8, 0x0080, 0x0040, 0, 0, 0),
        "truncated": protocol.l2cap_command(0x17, 9, b"\x01"),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_l2cap(1, pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("l2cap_credit", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("l2cap_malformed", "Malformed L2CAP signaling frames", Level.FUZZ, requires=("classic",), timeout=40)
async def l2cap_malformed(context: Context) -> ProbeResult:
    await _classic(context)
    cases = {
        "unknown-code": protocol.l2cap_command(0x7F, 10),
        "zero-length": protocol.l2cap_command(0x02, 11),
        "short-connect": protocol.l2cap_command(0x02, 12, b"\x01"),
        "huge-length": protocol.l2cap_command(0x02, 13, b"\x00" * 300),
        "bad-identifier": protocol.l2cap_connect(0, 0x0001),
        "config-truncated": protocol.l2cap_command(0x04, 14, b"\x01"),
        "disconnect-short": protocol.l2cap_command(0x06, 15, b"\x01"),
        "info-short": protocol.l2cap_command(0x0A, 16, b"\x01"),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_l2cap(1, pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.15)
    return ProbeResult("l2cap_malformed", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("l2cap_config", "Malformed configuration options", Level.FUZZ, requires=("classic",), timeout=40)
async def l2cap_config(context: Context) -> ProbeResult:
    await _classic(context)
    options = {
        "mtu": bytes([0x01, 0x02, 0xFF, 0xFF]),
        "flush": bytes([0x02, 0x02, 0xFF, 0xFF]),
        "qos": bytes([0x03, 0x16]) + b"\xff" * 22,
        "retransmission": bytes([0x04, 0x09]) + b"\xff" * 9,
        "unknown": bytes([0x7F, 0x03, 0x01, 0x02, 0x03]),
        "truncated": bytes([0x01, 0x04, 0x00]),
    }
    responses = {}
    for name, option in options.items():
        response = await context.transport.send_l2cap(1, protocol.l2cap_config_request(20, 0x0040, option), timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.15)
    return ProbeResult("l2cap_config", Status.OK, f"{len(responses)} options sent", "info", responses)
