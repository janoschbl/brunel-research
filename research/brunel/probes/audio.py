# avrcp, a2dp, and le audio probes

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe

AVCTP_PSM = 0x0017
AVDTP_PSM = 0x0019
BAP_SERVICE = "0000184e-0000-1000-8000-00805f9b34fb"
BASS_SERVICE = "0000184f-0000-1000-8000-00805f9b34fb"


def avctp(payload: bytes, transaction: int = 0) -> bytes:
    return bytes([(transaction & 0x0F) << 4, 0x11, 0x0E]) + payload


def avrcp_get_capabilities(capability: int = 0x02, count: int = 0xFF) -> bytes:
    return bytes([0x10, capability, count])


def avrcp_get_player_settings(attributes: bytes) -> bytes:
    return bytes([0x12, len(attributes)]) + attributes


@probe("avrcp_probe", "AVRCP capabilities and 255-attribute settings request", Level.FUZZ, requires=("classic",), timeout=35)
async def avrcp_probe(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    channel = await context.transport.connect_psm(AVCTP_PSM, timeout=5.0)
    if channel is None:
        return ProbeResult("avrcp_probe", Status.SKIPPED, "AVCTP PSM not open")
    responses = {}
    for name, payload in {
        "capabilities": avrcp_get_capabilities(),
        "settings-255": avrcp_get_player_settings(bytes(range(1, 0x100))),
        "settings-truncated": bytes([0x12, 0xFF, 0x01]),
    }.items():
        response = await context.transport.send_l2cap(channel, avctp(payload), timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.2)
    return ProbeResult("avrcp_probe", Status.OK, f"{sum(v is not None for v in responses.values())}/3 answered", "info", responses)


@probe("a2dp_probe", "AVDTP discover and get capabilities", Level.FUZZ, requires=("classic",), timeout=35)
async def a2dp_probe(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    channel = await context.transport.connect_psm(AVDTP_PSM, timeout=5.0)
    if channel is None:
        return ProbeResult("a2dp_probe", Status.SKIPPED, "AVDTP PSM not open")
    responses = {}
    for name, payload in {
        "discover": bytes([0x00, 0x01]),
        "get-capabilities": bytes([0x00, 0x02, 0x00]),
        "malformed": bytes([0x00, 0x02]),
    }.items():
        response = await context.transport.send_l2cap(channel, payload, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.2)
    return ProbeResult("a2dp_probe", Status.OK, f"{sum(v is not None for v in responses.values())}/3 answered", "info", responses)


@probe("bap_probe", "LE Audio BAP/BASS service presence", Level.READ, requires=("gatt",), timeout=30, needs_connection=True)
async def bap_probe(context: Context) -> ProbeResult:
    services = await context.ensure_services()
    uuids = {service.uuid for service in services}
    found = {"bap": BAP_SERVICE in uuids, "bass": BASS_SERVICE in uuids}
    if not any(found.values()):
        return ProbeResult("bap_probe", Status.SKIPPED, "no BAP or BASS service", "info", found)
    return ProbeResult("bap_probe", Status.FINDING, f"LE Audio services present: {found}", "info", found)


@probe("bass_probe", "Read BASS Broadcast Receive State", Level.READ, requires=("gatt",), timeout=30, needs_connection=True)
async def bass_probe(context: Context) -> ProbeResult:
    await context.ensure_services()
    if not context.has_service(BASS_SERVICE):
        return ProbeResult("bass_probe", Status.SKIPPED, "no BASS service")
    values = {}
    for characteristic in context.characteristics.values():
        for item in characteristic:
            if item.readable:
                try:
                    values[item.uuid] = (await context.read(item.uuid)).hex()
                except Exception as error:
                    values[item.uuid] = f"error: {error}"
    return ProbeResult("bass_probe", Status.FINDING, f"{len(values)} BASS values read", "info", values)
