# radio transport abstraction, bumble and mock

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from . import protocol


@dataclass
class Advertisement:
    address: str
    rssi: int
    data: bytes
    address_type: int | None = None
    name: str | None = None
    connectable: bool | None = None
    legacy: bool | None = None
    timestamp: float = field(default_factory=time.time)
    phy: int | None = None
    sid: int | None = None
    tx_power: int | None = None

    @property
    def structures(self) -> protocol.Structures:
        return protocol.parse_structures(self.data)

    @property
    def decoded(self) -> protocol.Decoded:
        return protocol.decode_bus(self.structures)

    @property
    def candidate(self) -> str | None:
        return protocol.candidate_reason(self.structures)


@dataclass
class Characteristic:
    handle: int
    uuid: str
    properties: int
    value_handle: int | None = None
    descriptors: list[tuple[int, str]] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        return bool(self.properties & 0x02)

    @property
    def writable_without_response(self) -> bool:
        return bool(self.properties & 0x04)

    @property
    def writable(self) -> bool:
        return bool(self.properties & 0x08)

    @property
    def writable_any(self) -> bool:
        return bool(self.properties & 0x0C)

    @property
    def notifiable(self) -> bool:
        return bool(self.properties & 0x10)

    @property
    def indicatable(self) -> bool:
        return bool(self.properties & 0x20)


@dataclass
class Service:
    handle: int
    uuid: str
    characteristics: list[Characteristic] = field(default_factory=list)


@dataclass
class ConnectionInfo:
    address: str
    transport: str
    mtu: int = 23
    encrypted: bool = False
    authenticated: bool = False
    bonded: bool = False


class TransportError(RuntimeError):
    pass


class Transport:
    def _on_gatt_pdu(self, connection, pdu) -> None:
        self._att_queue.put_nowait(pdu)
        self._original_on_gatt_pdu(connection, pdu)

    def _on_l2cap_pdu(self, connection, cid, pdu) -> None:
        self._l2cap_queue.put_nowait((cid, pdu))
        self._original_on_l2cap_pdu(connection, cid, pdu)

    async def start_scan(self, callback: Callable[[Advertisement], Any]) -> None:
        raise NotImplementedError

    async def stop_scan(self) -> None:
        raise NotImplementedError

    async def connect(self, address: str, timeout: float = 20.0, classic: bool = False) -> ConnectionInfo:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def discover(self) -> list[Service]:
        raise NotImplementedError

    async def read(self, handle: int) -> bytes:
        raise NotImplementedError

    async def read_uuid(self, uuid: str) -> bytes:
        raise NotImplementedError

    async def read_blob(self, handle: int, offset: int) -> bytes:
        raise NotImplementedError

    async def write(self, handle: int, value: bytes, response: bool = True) -> None:
        raise NotImplementedError

    async def write_uuid(self, uuid: str, value: bytes, response: bool = True) -> None:
        raise NotImplementedError

    async def subscribe(self, handle: int, callback: Callable[[bytes], Any]) -> None:
        raise NotImplementedError

    async def pair(self) -> dict[str, Any]:
        raise NotImplementedError

    async def send_att(self, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        raise NotImplementedError

    async def send_att_command(self, pdu: bytes) -> None:
        # send an att command without a response pdu
        raise NotImplementedError

    async def request_mtu(self, mtu: int = 517, timeout: float = 3.0) -> int:
        # negotiate the att mtu and return it
        raise NotImplementedError

    async def send_l2cap(self, cid: int, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        raise NotImplementedError

    async def connect_psm(self, psm: int, timeout: float = 5.0) -> int | None:
        raise NotImplementedError

    async def sdp_search(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def sdp_raw(self, pdu: bytes, timeout: float = 3.0) -> bytes | None:
        raise NotImplementedError

    async def advertise(self, data: bytes, scan_response: bytes = b"", extended: bool = True) -> None:
        raise NotImplementedError

    async def stop_advertising(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class BumbleTransport(Transport):
    def __init__(self, transport_spec: str = "usb:0", name: str = "BrunelBench"):
        self.transport_spec = transport_spec
        self.name = name
        self._transport = None
        self._device = None
        self._connection = None
        self._peer = None
        self._att_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._l2cap_queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()
        self._scan_callback: Callable[[Advertisement], Any] | None = None
        self._classic = False
        self._advertising_set = None
        self._original_on_gatt_pdu = None
        self._original_on_l2cap_pdu = None

    async def open(self) -> None:
        from bumble.device import Device, DeviceConfiguration
        from bumble.transport import open_transport

        self._transport = await open_transport(self.transport_spec)
        config = DeviceConfiguration()
        config.load_from_dict(
            {"name": self.name, "address": "F0:00:00:00:00:01", "class_of_device": 0x000104}
        )
        self._device = Device.from_config_with_hci(
            config,
            self._transport.source,
            self._transport.sink,
        )
        from bumble import att

        self._original_on_gatt_pdu = self._device.on_gatt_pdu
        self._original_on_l2cap_pdu = self._device.l2cap_channel_manager.on_pdu
        self._device.l2cap_channel_manager.on_pdu = self._on_l2cap_pdu
        self._device.l2cap_channel_manager.register_fixed_channel(att.ATT_CID, self._on_gatt_pdu)
        await self._device.power_on()
        self._device.on("advertisement", self._on_advertisement)

    def _on_advertisement(self, advertisement) -> None:
        callback = self._scan_callback
        if callback is None:
            return
        address = str(advertisement.address)
        event = Advertisement(
            address=address,
            rssi=advertisement.rssi,
            data=bytes(advertisement.data),
            address_type=getattr(advertisement.address, "address_type", None),
            name=getattr(advertisement, "name", None),
            connectable=getattr(advertisement, "is_connectable", None),
            legacy=getattr(advertisement, "is_legacy", None),
            phy=getattr(advertisement, "primary_phy", None),
            sid=getattr(advertisement, "advertising_sid", None),
            tx_power=getattr(advertisement, "tx_power", None),
        )
        result = callback(event)
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)

    async def start_scan(self, callback: Callable[[Advertisement], Any]) -> None:
        self._scan_callback = callback
        await self._device.start_scanning(legacy=False, active=True, filter_duplicates=False)

    async def stop_scan(self) -> None:
        self._scan_callback = None
        with contextlib.suppress(Exception):
            await self._device.stop_scanning()

    async def connect(self, address: str, timeout: float = 20.0, classic: bool = False) -> ConnectionInfo:
        from bumble.core import PhysicalTransport

        self._classic = classic
        self._connection = await self._device.connect(
            address,
            transport=PhysicalTransport.BR_EDR if classic else PhysicalTransport.LE,
            timeout=timeout,
        )
        from bumble.device import Peer

        self._peer = Peer(self._connection)
        return ConnectionInfo(
            address=address,
            transport="br-edr" if classic else "le",
            mtu=getattr(self._connection, "att_mtu", 23) or 23,
            encrypted=bool(getattr(self._connection, "is_encrypted", False)),
        )

    async def disconnect(self) -> None:
        if self._connection is not None:
            with contextlib.suppress(Exception):
                await self._connection.disconnect()
        self._connection = None
        self._peer = None

    async def discover(self) -> list[Service]:
        services = await self._peer.discover_services()
        result = []
        for service in services:
            item = Service(handle=service.handle, uuid=str(service.uuid))
            for characteristic in await self._peer.discover_characteristics(service=service):
                item.characteristics.append(
                    Characteristic(
                        handle=characteristic.handle,
                        uuid=str(characteristic.uuid),
                        properties=characteristic.properties,
                        value_handle=characteristic.handle,
                    )
                )
            result.append(item)
        return result

    async def read(self, handle: int) -> bytes:
        return await self._peer.read_value(handle)

    async def read_uuid(self, uuid: str) -> bytes:
        values = await self._peer.read_characteristics_by_uuid(uuid)
        if not values:
            raise TransportError(f"characteristic {uuid} not found")
        return values[0]

    async def read_blob(self, handle: int, offset: int) -> bytes:
        return await self._peer.gatt_client.read_value(handle, offset)

    async def write(self, handle: int, value: bytes, response: bool = True) -> None:
        await self._peer.write_value(handle, value, with_response=response)

    async def write_uuid(self, uuid: str, value: bytes, response: bool = True) -> None:
        characteristics = await self._peer.get_characteristics_by_uuid(uuid)
        if not characteristics:
            raise TransportError(f"characteristic {uuid} not found")
        await self._peer.write_value(characteristics[0], value, with_response=response)

    async def subscribe(self, handle: int, callback: Callable[[bytes], Any]) -> None:
        characteristics = await self._peer.get_characteristics_by_uuid(handle)
        if not characteristics:
            raise TransportError(f"characteristic {handle} not found")
        await self._peer.subscribe(characteristics[0], callback)

    async def pair(self) -> dict[str, Any]:
        await self._connection.pair()
        return {
            "encrypted": bool(getattr(self._connection, "is_encrypted", False)),
            "authenticated": bool(getattr(self._connection, "is_authenticated", False)),
        }

    async def send_att(self, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        while not self._att_queue.empty():
            self._att_queue.get_nowait()
        self._connection.send_l2cap_pdu(4, pdu)
        try:
            return await asyncio.wait_for(self._att_queue.get(), timeout)
        except TimeoutError:
            return None

    async def send_att_command(self, pdu: bytes) -> None:
        self._connection.send_l2cap_pdu(4, pdu)
        await asyncio.sleep(0)

    async def request_mtu(self, mtu: int = 517, timeout: float = 3.0) -> int:
        response = await self.send_att(protocol.att_mtu_request(mtu), timeout)
        if not response or response[0] != 0x03 or len(response) < 3:
            return int(getattr(self._connection, "att_mtu", 23) or 23)
        negotiated = int.from_bytes(response[1:3], "little")
        return max(23, min(mtu, negotiated))

    async def send_l2cap(self, cid: int, pdu: bytes, timeout: float = 2.0) -> bytes | None:
        while not self._l2cap_queue.empty():
            self._l2cap_queue.get_nowait()
        self._connection.send_l2cap_pdu(cid, pdu)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                got_cid, response = await asyncio.wait_for(
                    self._l2cap_queue.get(), max(0.01, deadline - time.monotonic())
                )
            except TimeoutError:
                return None
            if got_cid == cid:
                return response
        return None

    async def connect_psm(self, psm: int, timeout: float = 5.0) -> int | None:
        from bumble import l2cap

        try:
            channel = await asyncio.wait_for(
                self._connection.create_l2cap_channel(l2cap.ClassicChannelSpec(psm)), timeout
            )
        except Exception:
            return None
        return channel.cid

    async def sdp_search(self) -> list[dict[str, Any]]:
        from bumble import sdp
        from bumble.core import UUID

        client = sdp.Client(self._connection)
        await client.connect()
        try:
            handles = await client.search_services([UUID.from_string("0100")])
            records = []
            for handle in handles:
                attributes = await client.get_attributes(handle, [(0, 0xFFFF)])
                records.append(
                    {
                        "handle": handle,
                        "attributes": [
                            {"id": attribute.id, "value": attribute.value.to_bytes().hex()}
                            for attribute in attributes
                        ],
                    }
                )
            return records
        finally:
            with contextlib.suppress(Exception):
                await client.disconnect()

    async def sdp_raw(self, pdu: bytes, timeout: float = 3.0) -> bytes | None:
        from bumble import l2cap, sdp

        channel = await self._connection.create_l2cap_channel(l2cap.ClassicChannelSpec(sdp.SDP_PSM))
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        channel.sink = queue.put_nowait
        channel.write(pdu)
        try:
            return await asyncio.wait_for(queue.get(), timeout)
        except TimeoutError:
            return None
        finally:
            with contextlib.suppress(Exception):
                await channel.disconnect()

    async def advertise(self, data: bytes, scan_response: bytes = b"", extended: bool = True) -> None:
        from bumble.device import AdvertisingEventProperties, AdvertisingParameters

        properties = AdvertisingEventProperties(is_connectable=True, is_scannable=bool(scan_response), is_legacy=not extended)
        self._advertising_set = await self._device.create_advertising_set(
            advertising_parameters=AdvertisingParameters(advertising_event_properties=properties),
            advertising_data=data,
            scan_response_data=scan_response,
            auto_start=True,
        )

    async def stop_advertising(self) -> None:
        if self._advertising_set is not None:
            with contextlib.suppress(Exception):
                await self._advertising_set.stop()
            self._advertising_set = None

    async def close(self) -> None:
        await self.stop_advertising()
        await self.stop_scan()
        await self.disconnect()
        if self._device is not None:
            with contextlib.suppress(Exception):
                await self._device.power_off()
        if self._transport is not None:
            with contextlib.suppress(Exception):
                await self._transport.close()
