# passenger action writes and the https action path

from __future__ import annotations

import asyncio

from .. import backend, protocol
from ..bench import Context, Level, ProbeResult, Status, probe

KNOWN_ACTIONS = {
    0x01: "stop request",
    0x02: "boarding assistance",
    0x03: "door signal",
    0x04: "ride request",
}


@probe(
    "action_known",
    "Write the four known action bytes to 0x1f20",
    Level.ACTION,
    requires=("action",),
    timeout=40,
    needs_connection=True,
    destructive=True,
)
async def action_known(context: Context) -> ProbeResult:
    accepted = []
    errors = {}
    for value, label in KNOWN_ACTIONS.items():
        try:
            await context.write(protocol.ACTION_CHARACTERISTIC, bytes([value]))
            accepted.append(f"0x{value:02x} {label}")
        except Exception as error:
            errors[f"0x{value:02x}"] = str(error)
        await asyncio.sleep(1.2)
    if not accepted:
        return ProbeResult("action_known", Status.ERROR, "no action accepted", "info", {"errors": errors})
    return ProbeResult(
        "action_known",
        Status.FINDING,
        f"{len(accepted)}/4 accepted: " + ", ".join(accepted),
        "medium",
        {"accepted": accepted, "errors": errors},
    )


@probe(
    "action_matrix",
    "Write length and value matrix to 0x1f20",
    Level.ACTION,
    requires=("action",),
    timeout=90,
    needs_connection=True,
    destructive=True,
)
async def action_matrix(context: Context) -> ProbeResult:
    cases: list[bytes] = [bytes([value]) for value in range(0x00, 0x10)]
    cases += [b"", b"\x01\x00", b"\x01\x01", b"\xff" * 4, b"\xff" * 16, b"\xff" * 64, b"\xff" * 128, b"\xff" * 255]
    accepted: list[str] = []
    failed: dict[str, str] = {}
    for value in cases:
        try:
            await context.write(protocol.ACTION_CHARACTERISTIC, value, response=True)
            accepted.append(value.hex() or "empty")
        except Exception as error:
            failed[value.hex() or "empty"] = str(error)
        await asyncio.sleep(0.35)
    return ProbeResult(
        "action_matrix",
        Status.FINDING if accepted else Status.ERROR,
        f"{len(accepted)}/{len(cases)} writes accepted",
        "medium",
        {"accepted": accepted, "failed": failed},
    )


@probe(
    "action_long_write",
    "Prepare and execute a 512-byte long write to 0x1f20",
    Level.FUZZ,
    requires=("action",),
    timeout=60,
    needs_connection=True,
    destructive=True,
)
async def action_long_write(context: Context) -> ProbeResult:
    await context.ensure_services()
    characteristic = context.chars(protocol.ACTION_CHARACTERISTIC)[0]
    handle = characteristic.value_handle or characteristic.handle
    payload = bytes(range(256)) * 2
    chunk = max(20, context.mtu - 5)
    offset = 0
    responses = []
    while offset < len(payload):
        part = payload[offset : offset + chunk]
        pdu = protocol.att_prepare_write(handle, offset, part)
        response = await context.transport.send_att(pdu, timeout=3.0)
        responses.append(response.hex() if response else None)
        if response is None:
            break
        offset += len(part)
    execute = await context.transport.send_att(protocol.att_execute_write(1), timeout=3.0)
    return ProbeResult(
        "action_long_write",
        Status.FINDING if execute and execute[0] == 0x19 else Status.ERROR,
        f"prepared {offset}/{len(payload)} bytes, execute {execute.hex() if execute else 'timeout'}",
        "medium",
        {"responses": responses, "execute": execute.hex() if execute else None},
    )


@probe(
    "http_actions",
    "Send the three HTTPS action requests",
    Level.ACTION,
    timeout=45,
    destructive=True,
)
async def http_actions(context: Context) -> ProbeResult:
    replies = {}
    for action in ("stopRequest", "serviceRequest", "doorsignalRequest"):
        replies[action] = await backend.action(action, context.target.address)
    accepted = [name for name, reply in replies.items() if reply.get("accepted")]
    return ProbeResult(
        "http_actions",
        Status.FINDING if accepted else Status.OK,
        f"{len(accepted)}/3 accepted by the backend" if accepted else "backend did not confirm",
        "medium",
        {"replies": replies},
    )
