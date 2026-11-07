#!/usr/bin/env python3
# fake bus access module for phone-in-the-loop tests, not bluez

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import time
from pathlib import Path

from bumble import gatt
from bumble.device import Device
from bumble.transport import open_transport

ROUTE = "NeuenbekenHoltgrevenstraße\x1dRathausplatz\x1d"
ACTION = "00001f20-0000-1000-8000-00805f9b34fb"
ROUTE_CHAR = "00002020-0000-1000-8000-00805f9b34fb"
NAME = "00002a00-0000-1000-8000-00805f9b34fb"
PNP = "00002a50-0000-1000-8000-00805f9b34fb"


def bus_ad(line: str = "8", version: int = 0) -> bytes:
    payload = bytearray(16)
    payload[0:2] = struct.pack(">H", 18)
    payload[2] = version & 0x07
    payload[3:8] = bytes.fromhex("e121040101")
    payload[8] = 0x80
    payload[9 : 9 + len(line)] = line.encode()
    return b"\x02\x01\x06" + b"\x03\x03\x1f\x1f" + bytes([len(payload) + 3, 0xFF, 0x78, 0x7D]) + bytes(payload)


class Sim:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.log = Path(args.log)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.crashed = False
        self.version = 0

    def record(self, kind: str, **data: object) -> None:
        event = {"ts": time.time(), "kind": kind, **data}
        line = json.dumps(event, ensure_ascii=False)
        print(line, flush=True)
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    async def run(self) -> None:
        transport = await open_transport(self.args.transport)
        device = Device.from_config_with_hci(
            {"name": "ivi", "address": "78:C4:0E:AA:BB:CC", "class_of_device": 0x000104},
            transport.source,
            transport.sink,
        )
        await device.power_on()

        action = gatt.Characteristic(
            ACTION,
            gatt.Characteristic.Properties.WRITE | gatt.Characteristic.Properties.WRITE_WITHOUT_RESPONSE,
            gatt.Characteristic.Permissions.WRITEABLE,
            value=b"",
        )
        route = gatt.Characteristic(
            ROUTE_CHAR,
            gatt.Characteristic.Properties.READ,
            gatt.Characteristic.Permissions.READABLE,
            value=ROUTE.encode(),
        )
        name = gatt.Characteristic(
            NAME,
            gatt.Characteristic.Properties.READ,
            gatt.Characteristic.Permissions.READABLE,
            value=b"ivi",
        )
        pnp = gatt.Characteristic(
            PNP,
            gatt.Characteristic.Properties.READ,
            gatt.Characteristic.Permissions.READABLE,
            value=bytes([2]) + struct.pack("<HHH", 0x1D6B, 0x0246, (5 << 8) | 78),
        )
        service_changed = gatt.Characteristic(
            "00002a05-0000-1000-8000-00805f9b34fb",
            gatt.Characteristic.Properties.INDICATE,
            gatt.Characteristic.Permissions.READABLE,
            value=b"",
        )

        device.add_service(gatt.Service("00001f1f-0000-1000-8000-00805f9b34fb", [action]))
        device.add_service(gatt.Service("0000201f-0000-1000-8000-00805f9b34fb", [route]))
        device.add_service(gatt.Service("00001800-0000-1000-8000-00805f9b34fb", [name]))
        device.add_service(gatt.Service("00001801-0000-1000-8000-00805f9b34fb", [service_changed]))
        device.add_service(gatt.Service("0000180a-0000-1000-8000-00805f9b34fb", [pnp]))

        def on_write(connection, value: bytes) -> None:
            self.record("action", address=str(connection.peer_address), value=value.hex(), length=len(value))
            if self.args.crash_on_action and value and value[0] <= 0x04:
                asyncio.create_task(self.crash(f"action 0x{value[0]:02x}"))

        action.on("write", on_write)
        device.on("connection", lambda c: self.record("connect", address=str(c.peer_address)))
        device.on("disconnection", lambda c, reason: self.record("disconnect", address=str(c.peer_address), reason=reason))

        await device.start_advertising(advertising_data=bus_ad(), auto_restart=True)
        self.record("advertising", line="8", address=str(device.random_address))
        print("fake bus up. Ctrl-C to stop.", flush=True)

        while True:
            await asyncio.sleep(1)
            self.version = (self.version + 1) & 0x07
            if not self.crashed:
                await device.stop_advertising()
                await device.start_advertising(advertising_data=bus_ad(version=self.version), auto_restart=True)

    async def crash(self, reason: str) -> None:
        if self.crashed:
            return
        self.crashed = True
        self.record("crash", reason=reason)
        await asyncio.sleep(self.args.crash_seconds)
        self.crashed = False
        self.record("recovered", seconds=self.args.crash_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="usb:0")
    parser.add_argument("--log", default="lab/logs/phone-sim.jsonl")
    parser.add_argument("--crash-on-action", action="store_true")
    parser.add_argument("--crash-seconds", type=float, default=4)
    args = parser.parse_args()
    try:
        asyncio.run(Sim(args).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
