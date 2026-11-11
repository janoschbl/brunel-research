#!/usr/bin/env python3
"""Supervise one emulated bus module.

Layout:
  client --TCP--> supervisor --unix socket--> ARM app (qemu-arm-static)

The supervisor owns the advertisement timer, the power state and the restart
policy.  The app owns the GATT database and the vulnerable handler.  A crash
kills only the app; the supervisor brings it back after a short outage, which
is what a crash oracle and a canary brute force need.

Client lines:  ATT <hex>, SCAN, CONNECT, GET <file>, SET <file> <text>,
               STATUS, BOOT, SHUTDOWN, QUIT
Server lines:  ADV <hex>, ATT <hex>, EV <kind> <text>, DATA <file> <bytes>
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
import random
import resource
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "build" / "emulator"
QEMU = os.environ.get("QEMU_ARM", "qemu-arm-static")

FLAGS = b"\x02\x01\x06"
SERVICE = b"\x03\x03\x1f\x1f"


def no_core() -> None:
    """A brute force is a thousand crashes; keep the disk clean."""
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def bus_advertisement(name: str, line: str, version: int) -> bytes:
    payload = bytearray(16)
    payload[0:2] = struct.pack(">H", 18)
    payload[2] = version & 0x07
    payload[3:8] = bytes.fromhex("e121040101")
    payload[8] = 0x80
    payload[9 : 9 + len(line)] = line.encode()
    name_ad = bytes([len(name) + 1, 0x09]) + name.encode()[:28]
    return (
        FLAGS
        + SERVICE
        + name_ad
        + bytes([len(payload) + 3, 0xFF, 0x78, 0x7D])
        + bytes(payload)
    )


class Module:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.state = Path(args.state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.app_lock = threading.Lock()
        self.power = True
        self.version = 0
        self.started = time.time()
        self.crashes = 0
        self.runs = 0
        self.scanners: set[socket.socket] = set()
        self.att_clients: set[socket.socket] = set()
        self.app: socket.socket | None = None
        self.child: subprocess.Popen | None = None
        self.stopping = False
        self.symbols = self.pick_symbols()
        self.canary = args.canary or (
            f"{random.randrange(1, 256):02x}{random.randrange(256):02x}"
            f"{random.randrange(256):02x}00"
        )
        (self.state / "symbols.json").write_text(json.dumps(self.symbols) + "\n")
        (self.state / "canary").write_text(self.canary + "\n")
        (self.state / "pwned").unlink(missing_ok=True)
        (self.state / "out").unlink(missing_ok=True)
        for name, value in (
            ("name", "ivi"),
            ("route", "Heinz NixdorfWendeschleife\x1dHauptbahnhof\x1d"),
        ):
            if not (self.state / name).exists():
                (self.state / name).write_text(value)
        (self.state / "power").write_text("on")
        (self.state / "line").write_text(args.line)
        self.app_path = str(self.state / "app.sock")

    # ------------------------------------------------------------- helpers

    def pick_symbols(self) -> dict:
        rows = [
            json.loads(line)
            for line in (BUILD / "symbols.jsonl").read_text().splitlines()
            if line
        ]
        if self.args.profile == "plain":
            return next(row for row in rows if row["name"] == "plain")
        if self.args.profile == "canary":
            return next(row for row in rows if row["name"] == "canary")
        candidates = [row for row in rows if row["name"].startswith("pie_")]
        if self.args.variant is not None:
            return next(
                row for row in candidates if row["name"] == f"pie_{self.args.variant}"
            )
        return random.choice(candidates)

    def read_state(self, name: str, default: str = "") -> str:
        try:
            return (self.state / name).read_text()
        except OSError:
            return default

    def send(self, sock: socket.socket, line: bytes) -> None:
        with self.lock:
            try:
                sock.sendall(line + b"\n")
            except OSError:
                pass

    def broadcast(self, targets: set[socket.socket], line: bytes) -> None:
        for target in list(targets):
            self.send(target, line)

    # ------------------------------------------------------------ app side

    def start_app(self) -> None:
        if self.stopping:
            return
        binary = BUILD / self.symbols["name"]
        env = dict(os.environ)
        env["EMU_CANARY"] = self.canary
        env["EMU_STATE"] = str(self.state)
        if os.environ.get("EMU_DEBUG"):
            env["EMU_DEBUG"] = "1"
        self.runs += 1
        log = open(self.state / "app.log", "ab")
        self.child = subprocess.Popen(
            [QEMU, str(binary), "--listen", self.app_path, "--state", str(self.state)],
            env=env,
            stdout=log,
            stderr=log,
            preexec_fn=no_core,
        )
        threading.Thread(target=self.reap, args=(self.child,), daemon=True).start()

    def reap(self, child: subprocess.Popen) -> None:
        code = child.wait()
        if self.child is not child or self.stopping:
            return
        self.child = None
        with self.app_lock:
            if self.app is not None:
                try:
                    self.app.close()
                except OSError:
                    pass
                self.app = None
        crash = code not in (0, -signal.SIGTERM)
        if crash:
            self.crashes += 1
        self.broadcast(self.scanners, f"EV {'crash' if crash else 'down'} exit={code}".encode())
        if not self.power:
            return
        time.sleep(self.args.recovery_delay)
        self.start_app()

    def app_loop(self) -> None:
        """Keep exactly one connection to the app, reconnecting across restarts.

        The app serves one client at a time and returns to accept() on EOF, so
        the supervisor has to reattach after every disconnect instead of
        holding a dead hook.
        """
        while not self.stopping:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(self.app_path)
            except OSError:
                probe.close()
                time.sleep(0.05)
                continue
            with self.app_lock:
                self.app = probe
            self.broadcast(self.scanners, b"EV app-ready")
            self.broadcast(self.att_clients, b"EV app-ready")
            self.app_pump(probe)
            with self.app_lock:
                if self.app is probe:
                    self.app = None
            try:
                probe.close()
            except OSError:
                pass
            time.sleep(0.05)

    def app_pump(self, sock: socket.socket) -> None:
        """Read the app and fan ATT responses out to every ATT client."""
        while True:
            try:
                data = sock.recv(8192)
            except OSError:
                break
            if not data:
                break
            if os.environ.get("EMU_DEBUG"):
                print(f"pump {data[:400]!r}", flush=True)
            for line in data.split(b"\n"):
                if line:
                    self.broadcast(self.att_clients, line)

    # --------------------------------------------------------- client side

    def advert_loop(self) -> None:
        while not self.stopping:
            if self.power and self.child is not None and self.app is not None:
                self.version = (self.version + 1) & 0x07
                self.broadcast(
                    self.scanners,
                    b"ADV "
                    + bus_advertisement(
                        self.read_state("name", "ivi").strip(),
                        self.read_state("line", "11").strip(),
                        self.version,
                    ).hex().encode(),
                )
            time.sleep(0.25)

    def handle_line(self, sock: socket.socket, line: bytes) -> None:
        text = line.decode("utf-8", "replace")
        if text == "SCAN":
            self.scanners.add(sock)
            return
        if text == "CONNECT":
            self.att_clients.add(sock)
            self.send(sock, b"EV app-ready" if self.app is not None else b"EV app-wait")
            return
        if text == "STATUS":
            self.send(sock, json.dumps({
                "profile": self.args.profile,
                "variant": self.symbols["name"],
                "power": self.power,
                "crashes": self.crashes,
                "runs": self.runs,
                "uptime": round(time.time() - self.started, 1),
            }).encode())
            return
        if text == "BOOT":
            if not self.power:
                self.power = True
                (self.state / "power").write_text("on")
                if self.child is None:
                    self.start_app()
            self.send(sock, b"EV boot")
            return
        if text == "SHUTDOWN":
            self.power = False
            (self.state / "power").write_text("off")
            child = self.child
            if child is not None:
                child.terminate()
            self.send(sock, b"EV shutdown")
            return
        if text.startswith("GET "):
            name = text[4:].strip()
            try:
                data = (self.state / name).read_bytes()
            except OSError:
                self.send(sock, b"EV get-miss " + name.encode())
            else:
                self.send(sock, b"DATA " + name.encode() + b" " + data)
            return
        if text.startswith("SET "):
            _, name, value = text.split(" ", 2)
            (self.state / name).write_text(value)
            self.send(sock, b"EV set " + name.encode())
            return
        if text.startswith("ATT "):
            with self.app_lock:
                app = self.app
                if app is None:
                    return
                try:
                    app.sendall(line + b"\n")
                except OSError:
                    pass

    def serve(self, conn: socket.socket) -> None:
        self.send(conn, b"EV hello")
        buffer = b""
        while True:
            try:
                data = conn.recv(8192)
            except OSError:
                break
            if not data:
                break
            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self.handle_line(conn, line)
        self.scanners.discard(conn)
        self.att_clients.discard(conn)
        try:
            conn.close()
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--state", default="/tmp/brunel-emu")
    parser.add_argument("--profile", default="plain", choices=["plain", "canary", "pie"])
    parser.add_argument("--variant", type=int)
    parser.add_argument("--canary")
    parser.add_argument("--line", default="11")
    parser.add_argument("--recovery-delay", type=float, default=1.2)
    args = parser.parse_args()

    faulthandler.register(signal.SIGUSR1)
    module = Module(args)
    module.start_app()
    threading.Thread(target=module.app_loop, daemon=True).start()
    threading.Thread(target=module.advert_loop, daemon=True).start()

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(16)
    print(json.dumps({
        "port": args.port,
        "state": str(module.state),
        "profile": args.profile,
        "variant": module.symbols["name"],
        "canary": module.canary,
    }), flush=True)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while True:
            conn, _ = server.accept()
            threading.Thread(target=module.serve, args=(conn,), daemon=True).start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        module.stopping = True
        if module.child is not None:
            module.child.terminate()
        server.close()


if __name__ == "__main__":
    main()
