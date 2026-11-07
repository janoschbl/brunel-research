# raw att probes for the bluez gatt server

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe


async def _range(context: Context) -> tuple[int, int]:
    services = await context.ensure_services()
    start = services[0].handle
    end = max((c.handle for s in services for c in s.characteristics), default=start + 1)
    return start, end


@probe("att_mtu", "Exchange a 517-byte ATT MTU", Level.FUZZ, requires=("gatt",), timeout=15, needs_connection=True)
async def att_mtu(context: Context) -> ProbeResult:
    response = await context.transport.send_att(protocol.att_mtu_request(517), timeout=3.0)
    if response and response[0] == 0x03:
        mtu = int.from_bytes(response[1:3], "little")
        return ProbeResult("att_mtu", Status.FINDING, f"MTU accepted: {mtu}", "info", {"response": response.hex()})
    return ProbeResult("att_mtu", Status.OK, f"response {response.hex() if response else 'timeout'}", "info")


@probe("att_find_info", "Malformed Find Information requests", Level.FUZZ, requires=("gatt",), timeout=30, needs_connection=True)
async def att_find_info(context: Context) -> ProbeResult:
    start, end = await _range(context)
    cases = {
        "valid": protocol.att_find_information(start, end),
        "reversed": protocol.att_find_information(end, start),
        "zero": protocol.att_find_information(0, 0),
        "max": protocol.att_find_information(0xFFFF, 0xFFFF),
        "truncated": protocol.att_pdu(0x04, b"\x01"),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_att(pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("att_find_info", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("att_find_by_type", "Malformed Find By Type Value requests", Level.FUZZ, requires=("gatt",), timeout=30, needs_connection=True)
async def att_find_by_type(context: Context) -> ProbeResult:
    start, end = await _range(context)
    cases = {
        "primary": protocol.att_find_by_type_value(start, end, 0x2800, b""),
        "truncated": protocol.att_pdu(0x06, b"\x01\x00"),
        "reversed": protocol.att_find_by_type_value(end, start, 0x2800, b""),
        "max": protocol.att_find_by_type_value(0xFFFF, 0xFFFF, 0xFFFF, b"\xff" * 8),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_att(pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("att_find_by_type", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("att_read_by_type", "Malformed Read By Type requests", Level.FUZZ, requires=("gatt",), timeout=30, needs_connection=True)
async def att_read_by_type(context: Context) -> ProbeResult:
    start, end = await _range(context)
    cases = {
        "uuid16": protocol.att_read_by_type(start, end, 0x2803),
        "uuid128": protocol.att_read_by_type(start, end, bytes(range(16))),
        "truncated": protocol.att_pdu(0x08, b"\x01\x00"),
        "reversed": protocol.att_read_by_type(end, start, 0x2803),
        "zero": protocol.att_read_by_type(0, 0, 0x2803),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_att(pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("att_read_by_type", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("att_read_by_group", "Malformed Read By Group Type requests", Level.FUZZ, requires=("gatt",), timeout=30, needs_connection=True)
async def att_read_by_group(context: Context) -> ProbeResult:
    start, end = await _range(context)
    cases = {
        "primary": protocol.att_read_by_group_type(start, end, 0x2800),
        "truncated": protocol.att_pdu(0x10, b"\x01\x00"),
        "reversed": protocol.att_read_by_group_type(end, start, 0x2800),
        "unknown": protocol.att_read_by_group_type(start, end, 0x1234),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_att(pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("att_read_by_group", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("att_prepare_write", "Prepare Write with extreme offsets and 512 bytes", Level.FUZZ, requires=("action",), timeout=45, needs_connection=True)
async def att_prepare_write(context: Context) -> ProbeResult:
    await context.ensure_services()
    characteristic = context.chars(protocol.ACTION_CHARACTERISTIC)[0]
    handle = characteristic.value_handle or characteristic.handle
    cases = {
        "offset0": protocol.att_prepare_write(handle, 0, b"\x01\x02\x03"),
        "offset512": protocol.att_prepare_write(handle, 512, b"\xff" * 16),
        "offset65535": protocol.att_prepare_write(handle, 0xFFFF, b"\xff" * 16),
        "value512": protocol.att_prepare_write(handle, 0, b"\xaa" * 512),
        "badhandle": protocol.att_prepare_write(0xFFFF, 0, b"\x01"),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_att(pdu, timeout=3.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.15)
    execute = await context.transport.send_att(protocol.att_execute_write(1), timeout=3.0)
    responses["execute"] = execute.hex() if execute else None
    return ProbeResult("att_prepare_write", Status.OK, f"{len(responses)} cases sent", "info", responses)


@probe("att_invalid_handles", "Invalid and boundary handles", Level.FUZZ, requires=("gatt",), timeout=30, needs_connection=True)
async def att_invalid_handles(context: Context) -> ProbeResult:
    cases = {
        "read0": protocol.att_read(0x0000),
        "readffff": protocol.att_read(0xFFFF),
        "readblob": protocol.att_read_blob(0xFFFF),
        "write0": protocol.att_write_request(0x0000, b"\x01"),
        "confirm": protocol.att_handle_value_confirmation(0xFFFF),
    }
    responses = {}
    for name, pdu in cases.items():
        response = await context.transport.send_att(pdu, timeout=2.0)
        responses[name] = response.hex() if response else None
        await asyncio.sleep(0.1)
    return ProbeResult("att_invalid_handles", Status.OK, f"{sum(v is not None for v in responses.values())}/{len(cases)} answered", "info", responses)


@probe("att_sequence", "Rapid mixed ATT request sequence", Level.FUZZ, requires=("gatt",), timeout=45, needs_connection=True)
async def att_sequence(context: Context) -> ProbeResult:
    start, end = await _range(context)
    pdus = [
        protocol.att_mtu_request(64),
        protocol.att_find_information(start, end),
        protocol.att_read_by_type(start, end, 0x2803),
        protocol.att_read(start),
        protocol.att_read_by_group_type(start, end, 0x2800),
        protocol.att_find_by_type_value(start, end, 0x2800, b""),
        protocol.att_read_by_type(start, end, bytes(range(16))),
        protocol.att_read_blob(0),
    ]
    answered = 0
    for _ in range(4):
        for pdu in pdus:
            response = await context.transport.send_att(pdu, timeout=1.0)
            answered += response is not None
    return ProbeResult("att_sequence", Status.OK, f"{answered}/{len(pdus) * 4} answered", "info")
