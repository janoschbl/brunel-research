# probe registry, scheduler, and crash watchdog

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable

from . import protocol
from .store import Store
from .transport import Advertisement, Service, Transport, TransportError


class Level(IntEnum):
    PASSIVE = 0
    READ = 1
    ACTION = 2
    FUZZ = 3
    DOS = 4

    @classmethod
    def parse(cls, value: str) -> "Level":
        return cls[value.upper()]


class Status(str):
    OK = "ok"
    FINDING = "finding"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"
    CRASH = "crash"
    BLOCKED = "blocked"


@dataclass
class ProbeSpec:
    id: str
    title: str
    level: Level
    run: Callable[["Context"], Awaitable["ProbeResult"]]
    requires: tuple[str, ...] = ()
    timeout: float = 30.0
    cve: str | None = None
    description: str = ""
    destructive: bool = False
    needs_connection: bool = False


@dataclass
class ProbeResult:
    probe: str
    status: str
    summary: str
    severity: str = "info"
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    @property
    def finding(self) -> bool:
        return self.status == Status.FINDING


@dataclass
class Target:
    address: str
    advertisement: Advertisement
    decoded: protocol.Decoded
    fingerprint: dict[str, Any]
    services: list[Service] = field(default_factory=list)
    last_seen: float = field(default_factory=time.monotonic)
    first_seen: float = field(default_factory=time.monotonic)
    seen_count: int = 0
    crashes: int = 0
    recovered: int = 0
    downtime_ms: list[int] = field(default_factory=list)
    profile_id: str = ""

    @property
    def alive(self) -> bool:
        return time.monotonic() - self.last_seen < 5.0


class Context:
    def __init__(self, bench: "Bench", target: Target):
        self.bench = bench
        self.target = target
        self.transport = bench.transport
        self.store = bench.store
        self.services: list[Service] = []
        self.characteristics: dict[str, list[Any]] = {}
        self.connected = False
        self.transport_kind = "le"
        self.mtu = 23

    async def connect(self, classic: bool = False) -> None:
        kind = "br-edr" if classic else "le"
        if self.connected and self.transport_kind == kind:
            return
        if self.connected:
            await self.disconnect()
        info = await self.transport.connect(self.target.address, timeout=20.0, classic=classic)
        self.connected = True
        self.transport_kind = info.transport
        self.mtu = info.mtu
        self.store.event(
            "connection_state",
            {"status": 0, "newState": 2, "transport": info.transport, "mtu": info.mtu},
            profile_id=self.target.profile_id,
        )

    async def disconnect(self) -> None:
        if not self.connected:
            return
        self.connected = False
        await self.transport.disconnect()

    async def ensure_services(self) -> list[Service]:
        if self.services:
            return self.services
        await self.connect()
        self.services = await self.transport.discover()
        for service in self.services:
            for characteristic in service.characteristics:
                self.characteristics.setdefault(characteristic.uuid, []).append(characteristic)
        self.store.event(
            "gatt_services",
            {
                "services": [
                    {
                        "uuid": service.uuid,
                        "characteristics": [
                            {"uuid": c.uuid, "handle": c.handle, "properties": c.properties}
                            for c in service.characteristics
                        ],
                    }
                    for service in self.services
                ]
            },
            profile_id=self.target.profile_id,
        )
        return self.services

    def chars(self, uuid: str) -> list[Any]:
        return self.characteristics.get(uuid, [])

    def has_service(self, uuid: str) -> bool:
        return any(service.uuid == uuid for service in self.services)

    def has_char(self, uuid: str) -> bool:
        return bool(self.chars(uuid))

    async def read(self, uuid: str) -> bytes:
        await self.ensure_services()
        value = await self.transport.read_uuid(uuid)
        self.store.event(
            "gatt_read",
            {"characteristic": uuid, "status": 0, "bytes": value.hex(), "length": len(value)},
            profile_id=self.target.profile_id,
        )
        return value

    async def write(self, uuid: str, value: bytes, response: bool = True) -> None:
        await self.ensure_services()
        await self.transport.write_uuid(uuid, value, response)
        self.store.event(
            "gatt_write",
            {"characteristic": uuid, "bytes": value.hex(), "length": len(value), "response": response},
            profile_id=self.target.profile_id,
        )


class Watchdog:
    def __init__(self, store: Store, settle: float = 1.5, recovery: float = 20.0):
        self.store = store
        self.settle = settle
        self.recovery = recovery
        self.targets: dict[str, Target] = {}
        self._events: list[tuple[str, float]] = []

    def observe(self, advertisement: Advertisement) -> None:
        target = self.targets.get(advertisement.address)
        if target is None:
            return
        target.last_seen = time.monotonic()
        target.seen_count += 1
        self._events.append((advertisement.address, target.last_seen))

    async def after_probe(self, target: Target) -> tuple[bool, int]:
        before = target.last_seen
        await asyncio.sleep(self.settle)
        if target.last_seen > before:
            return False, 0
        started = time.monotonic()
        self.store.event(
            "crash_suspected",
            {"address": target.address, "silence_ms": int((started - before) * 1000)},
            profile_id=target.profile_id,
        )
        deadline = started + self.recovery
        while time.monotonic() < deadline:
            if target.last_seen > before:
                downtime = int((target.last_seen - before) * 1000)
                target.crashes += 1
                target.recovered += 1
                target.downtime_ms.append(downtime)
                self.store.event(
                    "crash_recovered",
                    {"address": target.address, "downtime_ms": downtime},
                    profile_id=target.profile_id,
                )
                return True, downtime
            await asyncio.sleep(0.2)
        target.crashes += 1
        self.store.event(
            "crash_unrecovered",
            {"address": target.address, "silence_ms": int((time.monotonic() - before) * 1000)},
            profile_id=target.profile_id,
        )
        return True, -1


class Bench:
    def __init__(
        self,
        transport: Transport,
        store: Store,
        level: Level = Level.READ,
        scan_seconds: float = 12.0,
        settle: float = 1.5,
        recovery: float = 20.0,
        probe_ids: list[str] | None = None,
        max_targets: int = 8,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.transport = transport
        self.store = store
        self.level = level
        self.scan_seconds = scan_seconds
        self.probes = [p for p in REGISTRY if probe_ids is None or p.id in probe_ids]
        self.probes.sort(key=lambda p: (p.level, p.id))
        self.watchdog = Watchdog(store, settle, recovery)
        self.max_targets = max_targets
        self.on_event = on_event
        self.targets: dict[str, Target] = {}
        self.results: list[ProbeResult] = []
        self._stop = asyncio.Event()

    def emit(self, event: dict[str, Any]) -> None:
        if self.on_event:
            result = self.on_event(event)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)

    async def _on_advertisement(self, advertisement: Advertisement) -> None:
        structures = advertisement.structures
        if advertisement.candidate is None:
            return
        decoded = protocol.decode_bus(structures)
        if decoded.simulator:
            return
        target = self.targets.get(advertisement.address)
        if target is None:
            if len(self.targets) >= self.max_targets:
                return
            target = Target(
                address=advertisement.address,
                advertisement=advertisement,
                decoded=decoded,
                fingerprint=protocol.fingerprint(advertisement.address, advertisement.name, None, decoded),
                profile_id=protocol.profile_id(self.store.session_id, advertisement.address),
            )
            self.targets[advertisement.address] = target
            self.watchdog.targets[advertisement.address] = target
            self.store.event(
                "target",
                {
                    "address": advertisement.address,
                    "rssi": advertisement.rssi,
                    "name": advertisement.name,
                    "candidate": advertisement.candidate,
                    "decoded": decoded.__dict__,
                    "fingerprint": target.fingerprint,
                },
                profile_id=target.profile_id,
            )
            self.emit({"type": "target", "target": target})
        else:
            target.advertisement = advertisement
            target.decoded = decoded
        target.last_seen = time.monotonic()
        target.seen_count += 1
        self.watchdog.observe(advertisement)
        self.store.advertisement(
            target.profile_id,
            {
                "receivedMs": int(advertisement.timestamp * 1000),
                "address": advertisement.address,
                "deviceName": advertisement.name,
                "rssi": advertisement.rssi,
                "bytes": advertisement.data.hex(),
                "length": len(advertisement.data),
                "hash": protocol.sha256(advertisement.data)[:16],
                "serviceUuids": structures.uuids,
                "manufacturer": {
                    f"0x{int.from_bytes(m[:2], 'little'):04x}": m[2:].hex()
                    for m in structures.manufacturer
                    if len(m) >= 2
                },
                "connectable": advertisement.connectable,
                "legacy": advertisement.legacy,
                "candidate": advertisement.candidate,
                "decoded": decoded.__dict__,
                "fingerprint": target.fingerprint,
            },
        )

    async def scan(self) -> None:
        await self.transport.start_scan(self._on_advertisement)
        try:
            await asyncio.wait_for(self._stop.wait(), self.scan_seconds)
        except TimeoutError:
            pass

    async def run_target(self, target: Target) -> None:
        context = Context(self, target)
        self.store.event("probe_plan", {"probes": [p.id for p in self.probes]}, profile_id=target.profile_id)
        for spec in self.probes:
            if self._stop.is_set():
                break
            if spec.level > self.level:
                continue
            missing = [requirement for requirement in spec.requires if not self._requirement(context, requirement)]
            if missing:
                result = ProbeResult(spec.id, Status.SKIPPED, f"missing: {', '.join(missing)}")
                self._record(target, spec, result)
                continue
            await self._run_probe(context, target, spec)
            if target.crashes and not target.alive:
                await self._wait_alive(target)
        await context.disconnect()

    def _requirement(self, context: Context, requirement: str) -> bool:
        if requirement == "gatt":
            return True
        if requirement == "route":
            return context.has_char(protocol.ROUTE_CHARACTERISTIC)
        if requirement == "action":
            return context.has_char(protocol.ACTION_CHARACTERISTIC)
        if requirement == "gatt-service":
            return context.has_service(protocol.GATT_SERVICE)
        if requirement == "classic":
            return True
        if requirement == "avrcp":
            return context.has_service("0000110e-0000-1000-8000-00805f9b34fb")
        if requirement == "a2dp":
            return context.has_service("0000110b-0000-1000-8000-00805f9b34fb")
        return True

    async def _run_probe(self, context: Context, target: Target, spec: ProbeSpec) -> None:
        started = time.monotonic()
        self.store.event(
            "probe_start",
            {"probe": spec.id, "title": spec.title, "level": spec.level.name, "cve": spec.cve},
            profile_id=target.profile_id,
        )
        self.emit({"type": "probe_start", "probe": spec.id, "target": target})
        try:
            if spec.needs_connection:
                await context.connect()
            result = await asyncio.wait_for(spec.run(context), spec.timeout)
        except TimeoutError:
            result = ProbeResult(spec.id, Status.TIMEOUT, f"no result after {spec.timeout:.0f} s")
        except TransportError as error:
            result = ProbeResult(spec.id, Status.ERROR, str(error))
        except Exception as error:
            result = ProbeResult(spec.id, Status.ERROR, f"{type(error).__name__}: {error}")
        result.duration_ms = int((time.monotonic() - started) * 1000)
        crashed, downtime = await self.watchdog.after_probe(target)
        if crashed:
            result.status = Status.CRASH
            result.severity = "high" if spec.level >= Level.FUZZ else "medium"
            result.evidence["downtime_ms"] = downtime
            result.summary = (result.summary + " · " if result.summary else "") + (
                f"target stopped advertising for {downtime} ms" if downtime >= 0 else "target did not recover"
            )
        self._record(target, spec, result)

    def _record(self, target: Target, spec: ProbeSpec, result: ProbeResult) -> None:
        self.results.append(result)
        self.store.event(
            "probe_result",
            {
                "probe": spec.id,
                "title": spec.title,
                "status": result.status,
                "severity": result.severity,
                "summary": result.summary,
                "evidence": result.evidence,
                "duration_ms": result.duration_ms,
                "cve": spec.cve,
            },
            profile_id=target.profile_id,
        )
        if result.finding or result.status == Status.CRASH:
            self.store.event(
                "finding",
                {"probe": spec.id, "severity": result.severity, "summary": result.summary, "evidence": result.evidence},
                profile_id=target.profile_id,
            )
        self.emit({"type": "probe_result", "result": result, "target": target})

    async def _wait_alive(self, target: Target) -> None:
        deadline = time.monotonic() + self.watchdog.recovery
        while time.monotonic() < deadline and not target.alive:
            await asyncio.sleep(0.2)

    async def run(self) -> list[ProbeResult]:
        self.store.event(
            "bench_start",
            {"level": self.level.name, "scan_seconds": self.scan_seconds, "probes": [p.id for p in self.probes]},
        )
        try:
            await self.scan()
            for target in list(self.targets.values()):
                if self._stop.is_set():
                    break
                await self.run_target(target)
        finally:
            await self.transport.stop_scan()
        self.store.event("bench_stop", {"results": len(self.results), "targets": len(self.targets)})
        return self.results

    def stop(self) -> None:
        self._stop.set()

    def summary(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for result in self.results:
            by_status[result.status] = by_status.get(result.status, 0) + 1
        return {
            "session": self.store.session_id,
            "level": self.level.name,
            "targets": [
                {
                    "address": target.address,
                    "profile": target.profile_id,
                    "fingerprint": target.fingerprint,
                    "crashes": target.crashes,
                    "downtime_ms": target.downtime_ms,
                }
                for target in self.targets.values()
            ],
            "results": [result.__dict__ for result in self.results],
            "by_status": by_status,
            "findings": [result.__dict__ for result in self.results if result.finding or result.status == Status.CRASH],
        }


REGISTRY: list[ProbeSpec] = []


def probe(
    probe_id: str,
    title: str,
    level: Level,
    requires: tuple[str, ...] = (),
    timeout: float = 30.0,
    cve: str | None = None,
    description: str = "",
    destructive: bool = False,
    needs_connection: bool = False,
) -> Callable[[Callable[[Context], Awaitable[ProbeResult]]], Callable[[Context], Awaitable[ProbeResult]]]:
    def register(function: Callable[[Context], Awaitable[ProbeResult]]) -> Callable[[Context], Awaitable[ProbeResult]]:
        REGISTRY.append(
            ProbeSpec(
                id=probe_id,
                title=title,
                level=level,
                run=function,
                requires=requires,
                timeout=timeout,
                cve=cve,
                description=description,
                destructive=destructive,
                needs_connection=needs_connection,
            )
        )
        return function

    return register


from . import probes  # noqa: E402,F401
