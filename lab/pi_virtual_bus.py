#!/usr/bin/env python3
# virtual bus access module on the pi with the real bluez 5.78

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

BLUEZ = "org.bluez"
GATT_MANAGER = "org.bluez.GattManager1"
ADV_MANAGER = "org.bluez.LEAdvertisingManager1"
OM = "org.freedesktop.DBus.ObjectManager"
PROPS = "org.freedesktop.DBus.Properties"
GATT_SERVICE = "org.bluez.GattService1"
GATT_CHRC = "org.bluez.GattCharacteristic1"
ADV_IFACE = "org.bluez.LEAdvertisement1"

ROUTE = "NeuenbekenHoltgrevenstraße\x1dRathausplatz\x1d"
ACTION = "00001f20-0000-1000-8000-00805f9b34fb"
ROUTE_CHAR = "00002020-0000-1000-8000-00805f9b34fb"
NAME_CHAR = "00002a00-0000-1000-8000-00805f9b34fb"
PNP_CHAR = "00002a50-0000-1000-8000-00805f9b34fb"

MANUFACTURER = 0x7D78
PROTOCOL = bytes.fromhex("001203e1210401018038000000000000")


class InvalidArgs(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupported(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class Service(dbus.service.Object):
    def __init__(self, bus, index, uuid):
        self.path = f"/org/bluez/bus/service{index}"
        self.bus = bus
        self.uuid = uuid
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def add(self, characteristic):
        self.characteristics.append(characteristic)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def props(self):
        return {
            GATT_SERVICE: {
                "UUID": dbus.String(self.uuid),
                "Primary": dbus.Boolean(True),
                "Characteristics": dbus.Array([c.get_path() for c in self.characteristics], signature="o"),
            }
        }

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE:
            raise InvalidArgs()
        return self.props()[GATT_SERVICE]


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + f"/char{index}"
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.service = service
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def props(self):
        return {GATT_CHRC: {"Service": self.service.get_path(), "UUID": dbus.String(self.uuid), "Flags": dbus.Array([dbus.String(f) for f in self.flags], signature="s"), "Descriptors": dbus.Array([], signature="o")}}

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC:
            raise InvalidArgs()
        return self.props()[GATT_CHRC]

    @dbus.service.method(GATT_CHRC, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        raise NotSupported()

    @dbus.service.method(GATT_CHRC, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        raise NotSupported()


class ReadCharacteristic(Characteristic):
    def __init__(self, bus, index, uuid, value, service):
        super().__init__(bus, index, uuid, ["read"], service)
        self.value = value

    def ReadValue(self, options):
        return dbus.Array([dbus.Byte(b) for b in self.value], signature="y")


class ActionCharacteristic(Characteristic):
    def __init__(self, bus, index, service, on_write):
        super().__init__(bus, index, ACTION, ["write", "write-without-response"], service)
        self.on_write = on_write

    def WriteValue(self, value, options):
        data = bytes(int(b) for b in value)
        self.on_write(data)


class Application(dbus.service.Object):
    def __init__(self, bus, on_action):
        self.path = "/org/bluez/bus"
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        self._add(bus, 0, "00001f1f-0000-1000-8000-00805f9b34fb", lambda s: [ActionCharacteristic(bus, 0, s, on_action)])
        self._add(bus, 1, "0000201f-0000-1000-8000-00805f9b34fb", lambda s: [ReadCharacteristic(bus, 0, ROUTE_CHAR, ROUTE.encode(), s)])
        self._add(bus, 2, "0000180a-0000-1000-8000-00805f9b34fb", lambda s: [ReadCharacteristic(bus, 0, PNP_CHAR, bytes([2]) + bytes.fromhex("6b1d46024e05"), s)])

    def _add(self, bus, index, uuid, factory):
        service = Service(bus, index, uuid)
        for characteristic in factory(service):
            service.add(characteristic)
        self.services.append(service)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(OM, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        result = {}
        for service in self.services:
            result[service.get_path()] = service.props()
            for characteristic in service.characteristics:
                result[characteristic.get_path()] = characteristic.props()
        return result


class Advertisement(dbus.service.Object):
    def __init__(self, bus, path="/org/bluez/bus/adv"):
        self.path = path
        self.bus = bus
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def props(self):
        return {
            ADV_IFACE: {
                "Type": "peripheral",
                "ServiceUUIDs": dbus.Array(["00001f1f-0000-1000-8000-00805f9b34fb"], signature="s"),
                "ManufacturerData": dbus.Dictionary({dbus.UInt16(MANUFACTURER): dbus.Array([dbus.Byte(b) for b in PROTOCOL], signature="y")}, signature="qv"),
                "IncludeTxPower": dbus.Boolean(False),
            }
        }

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != ADV_IFACE:
            raise InvalidArgs()
        return self.props()[ADV_IFACE]

    @dbus.service.method(ADV_IFACE)
    def Release(self):
        print("advertisement released", flush=True)


class Bus:
    def __init__(self, adapter: str, crash_seconds: float):
        self.adapter = adapter
        self.crash_seconds = crash_seconds
        self.bus = dbus.SystemBus()
        self.app = Application(self.bus, self.on_action)
        self.adv = Advertisement(self.bus)
        self.adv_manager = dbus.Interface(self.bus.get_object(BLUEZ, adapter), ADV_MANAGER)
        self.gatt_manager = dbus.Interface(self.bus.get_object(BLUEZ, adapter), GATT_MANAGER)
        self.registered = False
        self.advertising = False
        self.crashed = False
        self.actions: list[str] = []

    def on_action(self, value: bytes) -> None:
        self.actions.append(value.hex())
        print(f"action {value.hex()}", flush=True)

    def register(self) -> None:
        if not self.registered:
            self.gatt_manager.RegisterApplication(self.app.get_path(), {}, reply_handler=lambda: None, error_handler=self.error)
            self.registered = True
        if not self.advertising:
            self.adv_manager.RegisterAdvertisement(self.adv.get_path(), {}, reply_handler=lambda: None, error_handler=self.error)
            self.advertising = True

    def error(self, error) -> None:
        print(f"error: {error}", flush=True)

    def crash(self) -> None:
        if self.crashed:
            return
        self.crashed = True
        print("crash: removing advertisement", flush=True)
        try:
            self.adv_manager.UnregisterAdvertisement(self.adv.get_path())
            self.advertising = False
        except Exception as error:
            print(error, flush=True)
        threading.Timer(self.crash_seconds, self.recover).start()

    def recover(self) -> None:
        print("recover: re-registering advertisement", flush=True)
        try:
            self.adv_manager.RegisterAdvertisement(self.adv.get_path(), {}, reply_handler=lambda: None, error_handler=self.error)
            self.advertising = True
        except Exception as error:
            print(error, flush=True)
        self.crashed = False


def find_adapter(bus, wanted: str | None) -> str | None:
    remote = dbus.Interface(bus.get_object(BLUEZ, "/"), OM)
    for path, props in remote.GetManagedObjects().items():
        if GATT_MANAGER not in props:
            continue
        if wanted and path != wanted:
            continue
        return path
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="/org/bluez/hci1")
    parser.add_argument("--crash-seconds", type=float, default=5)
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = Bus(args.adapter, args.crash_seconds)
    bus.register()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str) -> None:
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/status":
                self._send(200, json.dumps({"advertising": bus.advertising, "crashed": bus.crashed, "actions": bus.actions}))
            elif self.path == "/crash":
                bus.crash()
                self._send(200, "{}")
            else:
                self._send(404, "{}")

        def do_POST(self) -> None:
            if self.path == "/crash":
                bus.crash()
                self._send(200, "{}")
            else:
                self._send(404, "{}")

        def log_message(self, fmt: str, *a: object) -> None:
            pass

    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever, daemon=True).start()
    print(f"virtual bus on {args.adapter}, control http://0.0.0.0:{args.port}/", flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
