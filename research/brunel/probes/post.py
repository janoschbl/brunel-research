# post-exploitation and secondary service discovery

from __future__ import annotations

from ..bench import Context, Level, ProbeResult, Status, probe

BUSCORE_SERVICE = "0000c68f-0000-1000-8000-00805f9b34fb"
DFU_SERVICE = "0000fe59-0000-1000-8000-00805f9b34fb"
SPP_SERVICE = "00001101-0000-1000-8000-00805f9b34fb"


@probe("buscore_detect", "Look for the BusCore challenge service 0xc68f", Level.READ, requires=("gatt",), timeout=25, needs_connection=True)
async def buscore_detect(context: Context) -> ProbeResult:
    await context.ensure_services()
    if not context.has_service(BUSCORE_SERVICE):
        return ProbeResult("buscore_detect", Status.SKIPPED, "no 0xc68f service")
    values = {}
    for characteristic in context.characteristics.values():
        for item in characteristic:
            if item.readable:
                try:
                    values[item.uuid] = (await context.read(item.uuid)).hex()
                except Exception as error:
                    values[item.uuid] = f"error: {error}"
    return ProbeResult("buscore_detect", Status.FINDING, f"BusCore service present, {len(values)} values", "info", values)


@probe("dfu_detect", "Look for a Nordic DFU service", Level.READ, requires=("gatt",), timeout=20, needs_connection=True)
async def dfu_detect(context: Context) -> ProbeResult:
    await context.ensure_services()
    if not context.has_service(DFU_SERVICE):
        return ProbeResult("dfu_detect", Status.SKIPPED, "no DFU service")
    return ProbeResult("dfu_detect", Status.FINDING, "DFU service present", "info")


@probe("spp_detect", "Look for SPP in SDP and RFCOMM", Level.READ, requires=("classic",), timeout=30)
async def spp_detect(context: Context) -> ProbeResult:
    await context.connect(classic=True)
    records = await context.transport.sdp_search()
    handles = [record["handle"] for record in records]
    if not handles:
        return ProbeResult("spp_detect", Status.OK, "no SDP records")
    return ProbeResult("spp_detect", Status.FINDING, f"{len(handles)} SDP records, SPP check manual", "info", {"handles": handles})


@probe("post_inventory", "Collect every readable value for the report", Level.READ, requires=("gatt",), timeout=60, needs_connection=True)
async def post_inventory(context: Context) -> ProbeResult:
    await context.ensure_services()
    values = {}
    for characteristic in context.characteristics.values():
        for item in characteristic:
            if item.readable:
                try:
                    values[item.uuid] = (await context.read(item.uuid)).hex()
                except Exception as error:
                    values[item.uuid] = f"error: {error}"
    return ProbeResult("post_inventory", Status.OK, f"{len(values)} readable values", "info", values)
