# deterministic in-process bus module for tests and dry runs

from __future__ import annotations

import asyncio
import random
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import protocol
from .transport import Advertisement, Characteristic, ConnectionInfo, Service, Transport, TransportError

ROUTE_TEXT = "NeuenbekenHoltgrevenstraße\x1dRathausplatz\x1d"


@dataclass
class MockBus:
    address: str = "78:C4:0E:AA:BB:CC"
    name: str = "ivi"
    line: str = "8"
    version: int = 0
    rssi: int = -55
    bluez: str = "5.78"
    crash_seconds: float = 3.0
    crash_on_eir: bool = True
    crash_on_att_fuzz: bool = True
    crash_on_l2cap_fuzz: bool = False
    crash_on_action_fuzz: bool = False
    action_log: list[bytes] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    writes: list[tuple[str, bytes]] = field(default_factory=list)
    crashes: list[str] = field(default_factory=list)
    _crashed_until: float = 0.0
    _started: float = field(default_factory=time.monotonic)
    _seq: int = 0

    @property
    def crashed(self) -> bool:
        return time.monotonic() < self._crashed_until

    def crash(self, reason: str) -> None:
        self.crashes.append(reason)
        self._crashed_until = time.monotonic() + self.crash_seconds

    def advertisement(self) -> bytes:
        self._seq += 1
        self.version = (self.version + 1) & 0x07
        return protocol.bus_advertisement(self.line, self.version)

    def services(self) -> list[Service]:
        def char(handle: int, uuid: str, properties: int, descriptors: list[tuple[int, str]] | None = None) -> Characteristic:
            return Characteristic(handle=handle, uuid=uuid, properties=properties, value_handle=handle + 1, descriptors=descriptors or [])

        return [
            Service(0x0001, protocol.BUS_SERVICE, [char(0x0002, protocol.ACTION_CHARACTERISTIC, 0x08)]),
            Service(0x0010, protocol.ROUTE_SERVICE, [char(0x0011, protocol.ROUTE_CHARACTERISTIC, 0x02)]),
            Service(
                0x0020,
                "00001800-0000-1000-8000-00805f9b34fb",
                [
                    char(0x0021, protocol.DEVICE_NAME, 0x02),
                    char(0x0023, "00002a01-0000-1000-8000-00805f9b34fb", 0x02),
                ],
            ),
            Service(
                0x0030,
                protocol.GATT_SERVICE,
                [char(0x0031, protocol.SERVICE_CHANGED, 0x20, [(0x0032, "00002902-0000-1000-8000-00805f9b34fb")])],
            ),
            Service(
                0x0040,
                "0000180a-0000-1000-8000-00805f9b34fb",
                [char(0x0041, protocol.PNP_ID, 0x02), char(0x0043, protocol.FIRMWARE_REVISION, 0x02)],
            ),
        ]

    def read_value(self, uuid: str) -> bytes:
        self.reads.append(uuid)
        if uuid == protocol.ROUTE_CHARACTERISTIC:
            return ROUTE_TEXT.encode()
        if uuid == protocol.DEVICE_NAME:
            return self.name.encode()
        if uuid == protocol.PNP_ID:
            return bytes([2]) + struct.pack("<HHH", 0x1D6B, 0x0246, (5 << 8) | 78)
        if uuid == protocol.FIRMWARE_REVISION:
            return b"1.4.2"
        if uuid == "00002a01-0000-1000-8000-00805f9b34fb":
            return b"\x00\x00"
        return b""

    def write_value(self, uuid: str, value: bytes) -> None:
        self.writes.append((uuid, value))
        if uuid == protocol.ACTION_CHARACTERISTIC:
            self.action_log.append(value)
            if self.crash_on_action_fuzz and len(value) > 4:
                self.crash("action-fuzz")


class MockTransport(Transport):
    def __init__(self, bus: MockBus | None = None, interval: float = 0.2):
        self.bus = bus or MockBus()
        self.interval = interval
        self._scan_task: asyncio.Task | None = None
        self._connected = False
        self._services: list[Service] = []
        self._notify: Callable[[bytes], Any] | None = None
        self._l2cap_cid = 0x0040
        self._prepared: dict[int, bytearray] = {}
        self.advertised: bytes | None = None
        self.advertised_scan_response: bytes | None = None

    async def start_scan(self, callback: Callable[[Advertisement], Any]) -> None:
        async def loop() -> None:
            while True:
                if not self.bus.crashed:
                    event = Advertisement(
                        address=self.bus.address,
                        rssi=self.bus.rssi,
                        data=self.bus.advertisement(),
                        name=self.bus.name,
                        connectable=True,
                        legacy=False,
                    )
                    result = callback(event)
                    if asyncio.iscoroutine(result):
                        await result
                await asyncio.sleep(self.interval)

        self._scan_task = asyncio.create_task(loop())

    async def stop_scan(self) -> None:
        if self._scan_task:
            self._scan_task.cancel()
            with asyncio_suppress():
                await self._scan_task
            self._scan_task = None

    async def connect(self, address: str, timeout: float = 20.0, classic: bool = False) -> ConnectionInfo:
        if self.bus.crashed:
            raise TransportError("target crashed")
        if address.upper() != self.bus.address.upper():
            raise TransportError(f"unknown address {address}")
        self._connected = True
        self._services = self.bus.services()
        return ConnectionInfo(address=address, transport="br-edr" if classic else "le", mtu=247)

    async def disconnect(self) -> None:
        self._connected = False

    async def discover(self) -> list[Service]:
        if not self._connected:
            raise TransportError("not connected")
        return self._services

    def _find(self, handle: int) -> Characteristic:
        for service in self._services:
            for characteristic in service.characteristics:
                if characteristic.value_handle == handle or characteristic.handle == handle:
                    return characteristic
        raise TransportError(f"no characteristic at handle 0x{handle:04x}")

    async def read(self, handle: int) -> bytes:
        return self.bus.read_value(self._find(handle).uuid)

    async def read_uuid(self, uuid: str) -> bytes:
        return self.bus.read_value(uuid)

    async def read_blob(self, handle: int, offset: int) -> bytes:
        return (await self.read(handle))[offset:]

    async def write(self, handle: int, value: bytes, response: bool = True) -> None:
        self.bus.write_value(self._find(handle).uuid, value)

    async def write_uuid(self, uuid: str, value: bytes, response: bool = True) -> None:
        self.bus.write_value(uuid, value)

    async def subscribe(self, handle: int, callback: Callable[[bytes], Any]) -> None:
        self._notify = callback

    async def pair(self) -> dict[str, Any]:
        return {"encrypted": True, "authenticated": False, "bonded": True}

    async def send_att(self, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        if self.bus.crashed:
            return None
        opcode = pdu[0]
        if opcode == 0x02:
            peer = int.from_bytes(pdu[1:3], "little") if len(pdu) >= 3 else 23
            return bytes([0x03]) + struct.pack("<H", max(23, min(peer, 517)))
        if opcode == 0x12:
            handle, value = struct.unpack_from("<H", pdu, 1)[0], pdu[3:]
            self.bus.write_value(self._find(handle).uuid, value)
            return bytes([0x13])
        if opcode == 0x52:
            handle, value = struct.unpack_from("<H", pdu, 1)[0], pdu[3:]
            self.bus.write_value(self._find(handle).uuid, value)
            return None
        if opcode == 0x16:
            if self.bus.crash_on_att_fuzz and len(pdu) - 5 > 512:
                self.bus.crash("att-prepare-write")
                return None
            handle = struct.unpack_from("<H", pdu, 1)[0]
            value = pdu[5:]
            self._prepared.setdefault(handle, bytearray()).extend(value)
            return bytes([0x17]) + pdu[1:5] + value
        if opcode == 0x18:
            for handle, value in self._prepared.items():
                self.bus.write_value(self._find(handle).uuid, bytes(value))
            self._prepared.clear()
            return bytes([0x19])
        if opcode == 0x04:
            start, end = struct.unpack_from("<HH", pdu, 1)
            entries = b""
            for service in self._services:
                for characteristic in service.characteristics:
                    if start <= characteristic.handle <= end:
                        entries += struct.pack("<HB", characteristic.handle, 0x02) + bytes.fromhex("2803")[::-1]
            if not entries:
                return protocol.att_error(0x04, start, 0x0A)
            return bytes([0x05]) + entries
        if opcode == 0x06:
            if self.bus.crash_on_att_fuzz and len(pdu) < 7:
                self.bus.crash("att-find-by-type")
                return None
            return protocol.att_error(0x06, 0x0001, 0x0A)
        if opcode == 0x08:
            start, end = struct.unpack_from("<HH", pdu, 1)
            uuid = pdu[5:]
            if self.bus.crash_on_att_fuzz and len(uuid) not in (2, 16):
                self.bus.crash("att-read-by-type")
                return None
            return protocol.att_error(0x08, start, 0x0A)
        if opcode == 0x10:
            return protocol.att_error(0x10, 0x0001, 0x0A)
        return protocol.att_error(opcode, 0x0000, 0x06)

    async def send_att_command(self, pdu: bytes) -> None:
        await self.send_att(pdu, timeout=0.1)

    async def request_mtu(self, mtu: int = 517, timeout: float = 3.0) -> int:
        response = await self.send_att(protocol.att_mtu_request(mtu), timeout)
        if not response or response[0] != 0x03:
            return 247
        return int.from_bytes(response[1:3], "little")

    async def send_l2cap(self, cid: int, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        if self.bus.crashed:
            return None
        if cid == 1 and len(pdu) >= 4:
            code, ident = pdu[0], pdu[1]
            if self.bus.crash_on_l2cap_fuzz and code not in (0x02, 0x04, 0x06, 0x0A):
                self.bus.crash("l2cap-signaling")
                return None
            if code == 0x02:
                psm = struct.unpack_from("<H", pdu, 4)[0]
                return protocol.l2cap_connect_response(ident, self._l2cap_cid, 0x0040, 0 if psm in protocol.KNOWN_PSMS else 2)
            if code == 0x04:
                return protocol.l2cap_config_response(ident, self._l2cap_cid)
            if code == 0x0A:
                return protocol.l2cap_command(0x0B, ident, struct.pack("<HH", 1, 0))
        return None

    async def connect_psm(self, psm: int, timeout: float = 5.0) -> int | None:
        if self.bus.crashed:
            return None
        return self._l2cap_cid if psm in protocol.KNOWN_PSMS else None

    async def sdp_search(self) -> list[dict[str, Any]]:
        return [
            {
                "handle": 0x00010000,
                "attributes": [
                    {"id": 0x0000, "value": "35"},
                    {"id": 0x0001, "value": "35"},
                    {"id": 0x0004, "value": "35"},
                ],
            }
        ]

    async def sdp_raw(self, pdu: bytes, timeout: float = 3.0) -> bytes | None:
        return b"\x03\x00\x01\x00\x00\x00\x02\x00\x01"

    async def advertise(self, data: bytes, scan_response: bytes = b"", extended: bool = True) -> None:
        self.advertised = data
        self.advertised_scan_response = scan_response
        if self.bus.crash_on_eir and (len(data) >= 250 or len(scan_response) >= 250) and b"\xff" in data + scan_response:
            self.bus.crash("eir-overflow")

    async def stop_advertising(self) -> None:
        self.advertised = None

    async def close(self) -> None:
        await self.stop_scan()


class asyncio_suppress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return exc_type is not None and issubclass(exc_type, asyncio.CancelledError)


def random_bus(seed: int | None = None) -> MockBus:
    rng = random.Random(seed)
    return MockBus(
        address="78:C4:0E:%02X:%02X:%02X" % tuple(rng.randrange(256) for _ in range(3)),
        line=str(rng.randrange(1, 20)),
        rssi=rng.randrange(-80, -40),
    )
