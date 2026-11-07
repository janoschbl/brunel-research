#!/usr/bin/env python3
# end-to-end action target: bumble gatt server plus a vulnerable c handler
from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import struct
import time
from pathlib import Path

from bumble import gatt
from bumble.device import Device, DeviceConfiguration
from bumble.transport import open_transport

ROUTE = "Heinz NixdorfWendeschleife\x1dHauptbahnhof\x1d"
ACTION = "00001f20-0000-1000-8000-00805f9b34fb"
ROUTE_CHAR = "00002020-0000-1000-8000-00805f9b34fb"
NAME = "00002a00-0000-1000-8000-00805f9b34fb"
PNP = "00002a50-0000-1000-8000-00805f9b34fb"


def bus_ad(line: str = "11", version: int = 0) -> bytes:
    payload = bytearray(16)
    payload[0:2] = struct.pack(">H", 18)
    payload[2] = version & 0x07
    payload[3:8] = bytes.fromhex("e121040101")
    payload[8] = 0x80
    payload[9 : 9 + len(line)] = line.encode()
    return (
        b"\x02\x01\x06"
        + b"\x03\x03\x1f\x1f"
        + bytes([len(payload) + 3, 0xFF, 0x78, 0x7D])
        + bytes(payload)
    )


class Target:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.log = Path(args.log)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.lib = ctypes.CDLL(args.library)
        self.lib.handle_action.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self.lib.handle_action.restype = None
        self.handle = self.lib.handle_action
        self.gadget = ctypes.cast(self.lib.pop_rdi_ret, ctypes.c_void_p).value
        self.command = ctypes.cast(self.lib.action_command, ctypes.c_void_p).value
        self.system = ctypes.cast(ctypes.CDLL(None).system, ctypes.c_void_p).value
        self.addresses = {
            "gadget": self.gadget,
            "system": self.system,
            "command": self.command,
            "offset": 264,
        }

    def record(self, kind: str, **data: object) -> None:
        event = {"ts": time.time(), "kind": kind, **data}
        line = json.dumps(event, ensure_ascii=False)
        print(line, flush=True)
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    async def run(self) -> None:
        Path(self.args.addresses).write_text(json.dumps(self.addresses) + "\n")
        self.record("addresses", **self.addresses)

        transport = await open_transport(self.args.transport)
        config = DeviceConfiguration()
        config.load_from_dict(
            {
                "name": "ivi",
                "address": self.args.address,
                "class_of_device": 0x000104,
            }
        )
        device = Device.from_config_with_hci(config, transport.source, transport.sink)
        await device.power_on()

        def on_write(connection, value: bytes) -> None:
            self.record("action", value=value.hex(), length=len(value))
            raw = ctypes.create_string_buffer(value, len(value))
            print(f"calling handler {len(value)}", flush=True)
            self.handle(ctypes.cast(raw, ctypes.c_void_p), len(value))
            print("handler returned", flush=True)

        action = gatt.Characteristic(
            ACTION,
            gatt.Characteristic.Properties.WRITE,
            gatt.Characteristic.Permissions.WRITEABLE,
            value=b"",
        )
        action.on("write", on_write)
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

        device.add_service(gatt.Service("00001f1f-0000-1000-8000-00805f9b34fb", [action]))
        device.add_service(gatt.Service("0000201f-0000-1000-8000-00805f9b34fb", [route]))
        device.add_service(gatt.Service("00001800-0000-1000-8000-00805f9b34fb", [name]))
        device.add_service(gatt.Service("0000180a-0000-1000-8000-00805f9b34fb", [pnp]))

        await device.start_advertising(advertising_data=bus_ad(), auto_restart=True)
        self.record("advertising", address=self.args.address)
        print("action target up", flush=True)

        while True:
            await asyncio.sleep(3600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="tcp-client:127.0.0.1:9100")
    parser.add_argument("--address", default="F0:00:00:00:00:01")
    parser.add_argument("--library", default="lab/build/harness/libaction_vuln.so")
    parser.add_argument("--log", default="lab/logs/action-target.jsonl")
    parser.add_argument("--addresses", default="lab/logs/action-addresses.json")
    args = parser.parse_args()

    try:
        asyncio.run(Target(args).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
