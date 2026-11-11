# transport for the local armv7 bus module emulator

from __future__ import annotations

import asyncio
import struct
from typing import Any, Callable

from . import protocol
from .transport import (
    Advertisement,
    Characteristic,
    ConnectionInfo,
    Service,
    Transport,
    TransportError,
)


def _full_uuid(value: bytes) -> str:
    number = int.from_bytes(value, "little")
    return f"{number:08x}-0000-1000-8000-00805f9b34fb"


class EmulatorTransport(Transport):
    """Speaks the supervisor line protocol on loopback.

    The scan channel is separate from the ATT channel on purpose: a client
    disconnect must not stop the advertisements, exactly like a radio.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9100, address: str | None = None):
        self.host = host
        self.port = port
        self.address = address
        self._scan: asyncio.StreamReader | None = None
        self._scan_writer: asyncio.StreamWriter | None = None
        self._ctl: asyncio.StreamReader | None = None
        self._ctl_writer: asyncio.StreamWriter | None = None
        self._att: asyncio.StreamReader | None = None
        self._att_writer: asyncio.StreamWriter | None = None
        self._att_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._data_queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()
        self._events: list[dict[str, Any]] = []
        self._callback: Callable[[Advertisement], Any] | None = None
        self._scan_task: asyncio.Task | None = None
        self._att_task: asyncio.Task | None = None
        self.mtu = 23

    async def open(self) -> None:
        self._scan, self._scan_writer = await asyncio.open_connection(self.host, self.port)
        self._scan_writer.write(b"SCAN\n")
        await self._scan_writer.drain()
        self._ctl, self._ctl_writer = await asyncio.open_connection(self.host, self.port)
        # every connection starts with "EV hello"; drop it so _control reads own replies
        await asyncio.wait_for(self._ctl.readline(), 5.0)
        self._scan_task = asyncio.create_task(self._scan_loop())

    async def _scan_loop(self) -> None:
        assert self._scan is not None
        while True:
            line = await self._scan.readline()
            if not line:
                return
            text = line.decode("utf-8", "replace").strip()
            if text.startswith("ADV "):
                await self._on_advertisement(text[4:])
            elif text.startswith("EV "):
                self._events.append({"kind": text[3:]})
            elif text.startswith("DATA "):
                _, _, rest = text.partition(" ")
                name, _, value = rest.partition(" ")
                self._data_queue.put_nowait((name, value.encode()))

    async def _on_advertisement(self, hex_data: str) -> None:
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            return
        structures = protocol.parse_structures(data)
        name = None
        for ad_type, body in protocol.iter_ad_structures(data):
            if ad_type in (0x08, 0x09):
                name = body.decode("utf-8", "replace")
        event = Advertisement(
            address=self.address or "78:C4:0E:00:00:00",
            rssi=-55,
            data=data,
            name=name,
            connectable=True,
            legacy=False,
        )
        callback = self._callback
        if callback is not None:
            result = callback(event)
            if asyncio.iscoroutine(result):
                await result

    async def start_scan(self, callback: Callable[[Advertisement], Any]) -> None:
        self._callback = callback

    async def stop_scan(self) -> None:
        self._callback = None

    # ------------------------------------------------------------ att side

    async def _ensure_att(self) -> None:
        if self._att_writer is not None:
            return
        self._att, self._att_writer = await asyncio.open_connection(self.host, self.port)
        self._att_writer.write(b"CONNECT\n")
        await self._att_writer.drain()
        ready = False
        for _ in range(40):
            try:
                line = await asyncio.wait_for(self._att.readline(), 5.0)
            except (asyncio.TimeoutError, TimeoutError):
                break
            if not line:
                break
            if b"app-ready" in line:
                ready = True
                break
        if not ready:
            raise TransportError("emulator app not ready")
        self.mtu = 23
        self._att_task = asyncio.create_task(self._att_loop())

    async def _att_loop(self) -> None:
        assert self._att is not None
        while True:
            line = await self._att.readline()
            if not line:
                self._att_queue.put_nowait(b"")
                return
            text = line.decode("utf-8", "replace").strip()
            if text.startswith("ATT "):
                body = text[4:]
                try:
                    pdu = bytes.fromhex(body)
                except ValueError:
                    pdu = b""
                if __debug__:
                    print(f"att<- {pdu.hex()}")
                self._att_queue.put_nowait(pdu)
            elif text.startswith("EV "):
                self._events.append({"kind": text[3:]})

    async def connect(self, address: str, timeout: float = 20.0, classic: bool = False) -> ConnectionInfo:
        await self._ensure_att()
        return ConnectionInfo(address=address, transport="le", mtu=23)

    async def disconnect(self) -> None:
        if self._att_task is not None:
            self._att_task.cancel()
            self._att_task = None
        if self._att_writer is not None:
            try:
                self._att_writer.close()
                await self._att_writer.wait_closed()
            except (OSError, ConnectionError):
                pass
        self._att_writer = None
        self._att = None
        while not self._att_queue.empty():
            self._att_queue.get_nowait()

    async def send_att(self, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        await self._ensure_att()
        assert self._att_writer is not None
        while not self._att_queue.empty():
            self._att_queue.get_nowait()
        self._att_writer.write(b"ATT " + pdu.hex().encode() + b"\n")
        await self._att_writer.drain()
        try:
            response = await asyncio.wait_for(self._att_queue.get(), timeout)
        except (asyncio.TimeoutError, TimeoutError):
            return None
        return response or None

    async def send_att_command(self, pdu: bytes) -> None:
        await self._ensure_att()
        assert self._att_writer is not None
        self._att_writer.write(b"ATT " + pdu.hex().encode() + b"\n")
        await self._att_writer.drain()

    async def request_mtu(self, mtu: int = 517, timeout: float = 3.0) -> int:
        response = await self.send_att(protocol.att_mtu_request(mtu), timeout)
        if not response or response[0] != 0x03 or len(response) < 3:
            self.mtu = 23
            return 23
        self.mtu = max(23, min(mtu, int.from_bytes(response[1:3], "little")))
        return self.mtu

    # ---------------------------------------------------------- discovery

    async def discover(self) -> list[Service]:
        found: list[tuple[Service, int]] = []
        start = 1
        while start <= 0xFFFF:
            response = await self.send_att(
                protocol.att_read_by_group_type(start, 0xFFFF, 0x2800)
            )
            if not response or response[0] != 0x11:
                break
            body = response[1:]
            offset = 0
            last = start
            while offset + 6 <= len(body):
                handle = struct.unpack_from("<H", body, offset)[0]
                end = struct.unpack_from("<H", body, offset + 2)[0]
                char_uuid = _full_uuid(body[offset + 4 : offset + 6])
                found.append((Service(handle, char_uuid), end))
                offset += 6
                last = end
            if last < start:
                break
            start = last + 1
        for service, end in found:
            start = service.handle + 1
            while start <= end:
                response = await self.send_att(
                    protocol.att_read_by_type(start, end, 0x2803)
                )
                if not response or response[0] != 0x09:
                    break
                body = response[1:]
                offset = 0
                last = start
                while offset + 7 <= len(body):
                    handle = struct.unpack_from("<H", body, offset)[0]
                    properties = body[offset + 2]
                    value_handle = struct.unpack_from("<H", body, offset + 3)[0]
                    uuid = _full_uuid(body[offset + 5 : offset + 7])
                    service.characteristics.append(
                        Characteristic(
                            handle=handle,
                            uuid=uuid,
                            properties=properties,
                            value_handle=value_handle,
                        )
                    )
                    offset += 7
                    last = handle
                if last < start:
                    break
                start = last + 1
        return [service for service, _ in found]

    async def find_handle(self, uuid: str) -> int | None:
        for service in await self.discover():
            for characteristic in service.characteristics:
                if characteristic.uuid.lower() == uuid.lower():
                    return characteristic.value_handle or characteristic.handle
        return None

    async def read(self, handle: int) -> bytes:
        response = await self.send_att(protocol.att_read(handle))
        if not response or response[0] != 0x0B:
            raise TransportError(f"read 0x{handle:04x} failed")
        return response[1:]

    async def read_uuid(self, uuid: str) -> bytes:
        handle = await self.find_handle(uuid)
        if handle is None:
            raise TransportError(f"characteristic {uuid} not found")
        return await self.read(handle)

    async def read_blob(self, handle: int, offset: int) -> bytes:
        response = await self.send_att(protocol.att_read_blob(offset))
        if not response or response[0] != 0x0D:
            raise TransportError("read blob failed")
        return response[1:]

    async def write(self, handle: int, value: bytes, response: bool = True) -> None:
        if response:
            pdu = protocol.att_write_request(handle, value)
            reply = await self.send_att(pdu)
            if not reply or reply[0] != 0x13:
                raise TransportError("write failed")
        else:
            await self.send_att_command(protocol.att_write_command(handle, value))

    async def write_uuid(self, uuid: str, value: bytes, response: bool = True) -> None:
        handle = await self.find_handle(uuid)
        if handle is None:
            raise TransportError(f"characteristic {uuid} not found")
        await self.write(handle, value, response)

    async def subscribe(self, handle: int, callback: Callable[[bytes], Any]) -> None:
        await self.write(handle + 1, b"\x01\x00")

    async def pair(self) -> dict[str, Any]:
        return {"encrypted": False, "authenticated": False, "bonded": False}

    async def send_l2cap(self, cid: int, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        return await self.send_att(pdu, timeout)

    async def connect_psm(self, psm: int, timeout: float = 5.0) -> int | None:
        return 0x40

    async def sdp_search(self) -> list[dict[str, Any]]:
        return []

    async def sdp_raw(self, pdu: bytes, timeout: float = 3.0) -> bytes | None:
        return None

    async def advertise(self, data: bytes, scan_response: bytes = b"", extended: bool = True) -> None:
        return None

    async def stop_advertising(self) -> None:
        return None

    # ---------------------------------------------------------- supervisor

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    async def _control(self, line: str) -> str:
        assert self._ctl_writer is not None and self._ctl is not None
        self._ctl_writer.write(line.encode() + b"\n")
        await self._ctl_writer.drain()
        reply = await asyncio.wait_for(self._ctl.readline(), 3.0)
        return reply.decode("utf-8", "replace").strip()

    async def get(self, name: str, timeout: float = 3.0) -> bytes:
        reply = await self._control("GET " + name)
        if reply.startswith("DATA "):
            _, _, value = reply[5:].partition(" ")
            return value.encode()
        raise TransportError(f"no data for {name}: {reply}")

    async def status(self) -> dict[str, Any]:
        import json

        reply = await self._control("STATUS")
        try:
            return json.loads(reply)
        except ValueError:
            return {"raw": reply}

    async def boot(self) -> None:
        await self._control("BOOT")

    async def shutdown(self) -> None:
        await self._control("SHUTDOWN")

    async def set_state(self, name: str, value: str) -> None:
        await self._control(f"SET {name} {value}")

    async def close(self) -> None:
        await self.disconnect()
        if self._scan_task is not None:
            self._scan_task.cancel()
            self._scan_task = None
        for writer in (self._scan_writer, self._ctl_writer):
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except (OSError, ConnectionError):
                    pass
        self._scan_writer = None
        self._ctl_writer = None
