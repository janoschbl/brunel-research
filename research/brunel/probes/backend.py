# read-only backend metadata probes

from __future__ import annotations

from .. import backend
from ..bench import Context, Level, ProbeResult, Status, probe


@probe("backend_lookup", "Read the lookup update list and database", Level.READ, timeout=30)
async def backend_lookup(context: Context) -> ProbeResult:
    updates = backend.updates()
    lookup = backend.lookup()
    evidence = {
        "updates": {k: updates.get(k) for k in ("code", "truncated", "error")},
        "lookup": {k: lookup.get(k) for k in ("code", "truncated", "error")},
        "lookup_bytes": len(lookup.get("body", "")),
    }
    if updates.get("error") and lookup.get("error"):
        return ProbeResult("backend_lookup", Status.ERROR, "backend unreachable", "info", evidence)
    return ProbeResult(
        "backend_lookup",
        Status.OK,
        f"updates HTTP {updates.get('code')}, lookup HTTP {lookup.get('code')}",
        "info",
        evidence,
    )


@probe("backend_vehicle", "Read the vehicle type for the address", Level.READ, timeout=20)
async def backend_vehicle(context: Context) -> ProbeResult:
    reply = backend.vehicle_type(context.target.address)
    if reply.get("error"):
        return ProbeResult("backend_vehicle", Status.ERROR, reply["error"], "info", reply)
    return ProbeResult(
        "backend_vehicle",
        Status.FINDING,
        f"HTTP {reply.get('code')}: {reply.get('body', '')[:120]}",
        "info",
        reply,
    )
