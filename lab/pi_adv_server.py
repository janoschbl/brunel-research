#!/usr/bin/env python3
# backpack advertiser with a small web control page

from __future__ import annotations

import argparse
import json
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import hci_adv

PAGE = """<!doctype html>
<html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brunel Backpack</title>
<style>
body{font:16px system-ui;background:#12101c;color:#e9e6f4;margin:0;padding:24px}
main{max-width:520px;margin:auto;display:grid;gap:16px}
button{font:600 1rem system-ui;padding:14px;border:0;border-radius:12px;background:#6ea8f0;color:#12101c}
button.stop{background:#f07a70}
pre{background:#221f33;padding:12px;border-radius:10px;overflow:auto}
</style>
<main><h1>Brunel Backpack</h1>
<p>252-Byte-EIR gegen den Bus. Starten, dann am Telefon den Bus beobachten.</p>
<button onclick="fetch('/start',{method:'POST'})">Start</button>
<button class="stop" onclick="fetch('/stop',{method:'POST'})">Stop</button>
<pre id="s">lade …</pre>
<script>setInterval(async()=>{document.getElementById('s').textContent=await (await fetch('/status')).text()},1000)</script>
</main></html>"""


class Advertiser:
    def __init__(self, index: int, handle: int, name_len: int):
        self.index = index
        self.handle = handle
        self.name_len = name_len
        self.running = False
        self.error: str | None = None
        self.sent = 0
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.error = None
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.running = False

    def _run(self) -> None:
        payload = bytes([self.name_len + 1, 0x09]) + b"\xff" * self.name_len
        payload = bytes([0x02, 0x01, 0x06, 0x03, 0x03, 0x1F, 0x1F]) + payload
        try:
            sock = socket.socket(hci_adv.AF_BLUETOOTH, socket.SOCK_RAW, hci_adv.BTPROTO_HCI)
            sock.bind((self.index,))
            sock.setsockopt(socket.SOL_HCI, socket.HCI_FILTER, struct.pack("<IIIH2x", 1 << 4, 0xFFFFFFFF, 0xFFFFFFFF, 0))
            status = hci_adv.command(sock, hci_adv.OCF_SET_EXT_ADV_PARAMS, hci_adv.params(self.handle))
            if status:
                raise RuntimeError(f"set params 0x{status:02x}")
            status = hci_adv.set_data(sock, self.handle, payload)
            if status:
                raise RuntimeError(f"set data 0x{status:02x}")
            status = hci_adv.enable(sock, self.handle, True)
            if status:
                raise RuntimeError(f"enable 0x{status:02x}")
            self.sent += 1
            while not self.stop_event.wait(1.0):
                pass
            hci_adv.enable(sock, self.handle, False)
            sock.close()
        except Exception as error:
            self.error = str(error)
        finally:
            self.running = False


def find_adapter() -> tuple[int, int] | None:
    for index in range(4):
        for handle in range(1, 4):
            try:
                sock = socket.socket(hci_adv.AF_BLUETOOTH, socket.SOCK_RAW, hci_adv.BTPROTO_HCI)
                sock.bind((index,))
                sock.setsockopt(socket.SOL_HCI, socket.HCI_FILTER, struct.pack("<IIIH2x", 1 << 4, 0xFFFFFFFF, 0xFFFFFFFF, 0))
                status = hci_adv.command(sock, hci_adv.OCF_SET_EXT_ADV_PARAMS, hci_adv.params(handle))
                sock.close()
                if status == 0:
                    return index, handle
            except OSError:
                continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=-1, help="-1 auto-detects a BLE 5 adapter")
    parser.add_argument("--name-len", type=int, default=250)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    handle = 1
    if args.index < 0:
        found = find_adapter()
        if found is None:
            raise SystemExit("no adapter with extended advertising found; power-cycle the BLE 5 dongle")
        args.index, handle = found
        print(f"using hci{args.index} handle {handle}", flush=True)
    advertiser = Advertiser(args.index, handle, args.name_len)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, kind: str = "text/plain") -> None:
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/":
                self._send(200, PAGE, "text/html")
            elif self.path == "/status":
                self._send(200, json.dumps({
                    "running": advertiser.running,
                    "error": advertiser.error,
                    "index": advertiser.index,
                    "name_len": advertiser.name_len,
                }))
            else:
                self._send(404, "not found")

        def do_POST(self) -> None:
            if self.path == "/start":
                advertiser.start()
                self._send(200, "started")
            elif self.path == "/stop":
                advertiser.stop()
                self._send(200, "stopped")
            else:
                self._send(404, "not found")

        def log_message(self, fmt: str, *args: object) -> None:
            print(fmt % args, flush=True)

    print(f"http://0.0.0.0:{args.port}/ index={args.index} name_len={args.name_len}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
