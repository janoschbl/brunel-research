# passive and read-only reconnaissance

from __future__ import annotations

import asyncio

from .. import protocol
from ..bench import Context, Level, ProbeResult, Status, probe


@probe(
    "fingerprint",
    "Read device name, PnP ID, and revision characteristics",
    Level.READ,
    requires=("gatt",),
    timeout=25,
    needs_connection=True,
)
async def fingerprint(context: Context) -> ProbeResult:
    await context.ensure_services()
    evidence: dict[str, object] = {"services": [s.uuid for s in context.services]}
    name = None
    for uuid in (protocol.DEVICE_NAME, protocol.MANUFACTURER_NAME, protocol.MODEL_NUMBER):
        if context.has_char(uuid):
            try:
                name = (await context.read(uuid)).decode("utf-8", "replace")
                evidence[uuid] = name
            except Exception as error:
                evidence[uuid] = f"error: {error}"
    pnp = None
    if context.has_char(protocol.PNP_ID):
        try:
            pnp = protocol.parse_pnp_id(await context.read(protocol.PNP_ID))
            evidence["pnp"] = pnp
        except Exception as error:
            evidence["pnp"] = f"error: {error}"
    for uuid, label in (
        (protocol.FIRMWARE_REVISION, "firmware"),
        (protocol.HARDWARE_REVISION, "hardware"),
        (protocol.SOFTWARE_REVISION, "software"),
    ):
        if context.has_char(uuid):
            try:
                evidence[label] = (await context.read(uuid)).decode("utf-8", "replace")
            except Exception as error:
                evidence[label] = f"error: {error}"
    context.target.fingerprint = protocol.fingerprint(context.target.address, name, pnp, context.target.decoded)
    bluez = pnp.get("bluez_guess") if pnp else None
    if bluez:
        return ProbeResult(
            "fingerprint",
            Status.FINDING,
            f"BlueZ {bluez} fingerprint via PnP ID; name {name!r}",
            "info",
            evidence,
        )
    return ProbeResult("fingerprint", Status.OK, f"name {name!r}", "info", evidence)


@probe(
    "gatt_enum",
    "Enumerate every service, characteristic, and descriptor",
    Level.READ,
    requires=("gatt",),
    timeout=45,
    needs_connection=True,
)
async def gatt_enum(context: Context) -> ProbeResult:
    services = await context.ensure_services()
    readable = [c for s in services for c in s.characteristics if c.readable]
    values: dict[str, str] = {}
    for characteristic in readable:
        if characteristic.uuid == protocol.ACTION_CHARACTERISTIC:
            continue
        try:
            value = await context.read(characteristic.uuid)
            values[characteristic.uuid] = value.hex()
        except Exception as error:
            values[characteristic.uuid] = f"error: {error}"
    descriptors = {
        s.uuid: [d.uuid for c in s.characteristics for d in c.descriptors]
        for s in services
        if any(c.descriptors for c in s.characteristics)
    }
    evidence = {
        "services": [
            {
                "uuid": s.uuid,
                "characteristics": [
                    {"uuid": c.uuid, "handle": c.handle, "properties": c.properties, "descriptors": [d.uuid for d in c.descriptors]}
                    for c in s.characteristics
                ],
            }
            for s in services
        ],
        "values": values,
        "descriptors": descriptors,
    }
    interesting = [
        uuid
        for uuid in values
        if uuid
        in {
            protocol.ROUTE_CHARACTERISTIC,
            protocol.PNP_ID,
            protocol.DEVICE_NAME,
            "0000c68f-0000-1000-8000-00805f9b34fb",
        }
    ]
    status = Status.FINDING if interesting else Status.OK
    return ProbeResult(
        "gatt_enum",
        status,
        f"{len(services)} services, {sum(len(s.characteristics) for s in services)} characteristics, {len(readable)} readable",
        "info",
        evidence,
    )


@probe(
    "route_read",
    "Read the full route text from 0x2020",
    Level.READ,
    requires=("route",),
    timeout=30,
    needs_connection=True,
)
async def route_read(context: Context) -> ProbeResult:
    raw = await context.read(protocol.ROUTE_CHARACTERISTIC)
    parsed = protocol.vehicle_text(raw)
    evidence = {"bytes": raw.hex(), "length": len(raw)}
    if parsed is None:
        return ProbeResult("route_read", Status.OK, f"{len(raw)} bytes, not a route text", "info", evidence)
    evidence.update({"destination": parsed.destination, "next_stop": parsed.next_stop, "rest": parsed.rest})
    return ProbeResult(
        "route_read",
        Status.FINDING,
        f"destination {parsed.destination!r}, next stop {parsed.next_stop!r}",
        "info",
        evidence,
    )


@probe(
    "service_changed",
    "Subscribe to the Service Changed indication 0x2a05",
    Level.READ,
    requires=("gatt-service",),
    timeout=20,
    needs_connection=True,
)
async def service_changed(context: Context) -> ProbeResult:
    await context.ensure_services()
    characteristics = context.chars(protocol.SERVICE_CHANGED)
    if not characteristics:
        return ProbeResult("service_changed", Status.SKIPPED, "0x2a05 not present")
    received: list[bytes] = []

    def on_value(value: bytes) -> None:
        received.append(value)

    await context.transport.subscribe(characteristics[0].handle, on_value)
    await asyncio.sleep(3)
    return ProbeResult(
        "service_changed",
        Status.OK,
        f"subscribed, {len(received)} indications in 3 s",
        "info",
        {"values": [v.hex() for v in received]},
    )


@probe(
    "pairing",
    "Pair, then re-enumerate the security state",
    Level.ACTION,
    requires=("gatt",),
    timeout=45,
    needs_connection=True,
)
async def pairing(context: Context) -> ProbeResult:
    await context.ensure_services()
    before = [s.uuid for s in context.services]
    try:
        state = await context.transport.pair()
    except Exception as error:
        return ProbeResult("pairing", Status.BLOCKED, f"pairing failed: {error}", "info", {"services_before": before})
    context.services = []
    context.characteristics = {}
    after = [s.uuid for s in await context.ensure_services()]
    evidence = {"state": state, "services_before": before, "services_after": after}
    return ProbeResult(
        "pairing",
        Status.FINDING,
        f"paired, encrypted={state.get('encrypted')}, authenticated={state.get('authenticated')}",
        "info",
        evidence,
    )


@probe(
    "psm_probe",
    "Probe common BR/EDR PSMs",
    Level.READ,
    requires=("classic",),
    timeout=40,
)
async def psm_probe(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    open_psms: dict[str, int] = {}
    for psm, label in protocol.KNOWN_PSMS.items():
        cid = await context.transport.connect_psm(psm, timeout=2.0)
        if cid is not None:
            open_psms[label] = psm
    if not open_psms:
        return ProbeResult("psm_probe", Status.OK, "no common PSM accepted", "info")
    return ProbeResult(
        "psm_probe",
        Status.FINDING,
        "open PSMs: " + ", ".join(f"{label} (0x{psm:04x})" for label, psm in open_psms.items()),
        "info",
        {"psms": open_psms},
    )
