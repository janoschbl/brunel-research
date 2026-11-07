# Lab

[English](README.md) · [Deutsch](../de/README.md)

Reproducible BlueZ 5.78 target for the bench. Two paths:

- **Host harness**: no root, no radio. Builds the vulnerable parser with ASan
  and proves CVE-2026-80186 in seconds.
- **Docker target**: full `bluetoothd` on `btvirt` with an attacker controller
  over TCP. Needs `/dev/vhci` and a privileged container.

## Host harness

```sh
lab/scripts/build-bluez.sh
lab/scripts/repro-eir.sh
```

`repro-eir.sh` runs the vulnerable parser, expects an ASan stack-buffer-overflow
at `name2utf8`, applies the upstream clamp, and expects a clean run. It prints
`PASS` only when both halves hold.

The primitive harness shows what the EIR bug actually does on stock 5.78: a
plain build survives, an ASan or FORTIFY build aborts. It also prints the leaked
run.

```sh
lab/scripts/eir-primitive.sh
```

The GATT database harness is separate:

```sh
lab/scripts/build-gatt-harness.sh
lab/build/harness/gatt_db_harness
```

## Docker

```sh
cd lab
LAB_MODE=eir docker compose up --build
```

The target exposes the attacker controller on `127.0.0.1:9000`. From the host:

```sh
research/.venv/bin/brunel bench --transport tcp-client:127.0.0.1:9000 --level dos
```

`LAB_MODE=gatt` starts `btgatt-server` instead of `bluetoothd` and the discovery
loop. Use it for the ATT and GATT probes; use `eir` for the advertisement
overflow and SDP/L2CAP.

Or run the bench from the host in one step:

```sh
lab/scripts/run-docker-bench.sh dos
```

Logs land in `lab/logs`.

## Phone-in-the-loop

Two scripts let the phone test against this PC:

```sh
sudo lab/scripts/run-phone-sim.sh usb:0
sudo lab/scripts/run-eir-target.sh
```

`run-phone-sim.sh` advertises a fake protocol-18 bus with the real GATT shape and
logs every read and action. Use it to validate the app before a field run.

`run-eir-target.sh` stops the system daemon, runs the ASan 5.78 `bluetoothd` on
`hci0`, and starts discovery. Use it to test the EIR payload over the air. The
phone's Android advertiser sends service data, not a complete local name, so a
negative result here is not a negative result for the bug.

If you have only one adapter and no rooted phone, use the PC as both sides:

```sh
sudo lab/scripts/self-eir.sh
```

It runs the ASan target, advertises the exact 255-byte payload through `btmgmt`,
and checks the log for an ASan crash. This is the full radio path on one
controller.

All three scripts need `sudo` and stop the system Bluetooth daemon for the
duration.

## Local without Docker

```sh
lab/scripts/run-local.sh eir
```

This needs `sudo` for `/dev/vhci` and `socat`.

## What the lab does and does not prove

The harness proves the parser bug in the exact 5.78 source. The Docker target
proves reachability through `bluetoothd` and the controller. Neither proves the
vendor build. The field bench records the vendor fingerprint and the crash
timing; the report keeps those separate from the lab result.

## Kernel matrix

The module kernel is unknown. `lab/kernel/` holds the matrix and the QEMU notes.
Do not assume 6.6. The L2CAP probes are best-effort against whatever kernel the
target runs; a negative result only means the path did not crash that build.

## Action ROP proof

`action-e2e.sh` runs the full 512-byte action path against a Bumble GATT server
with a 256-byte handler. It starts two linked `btvirt` controllers, so it needs
no root and no radio. The attack uses the normal `brunel rce` stage and must
print `PWNED-GATT`.

`action-rop.sh` proves the x86-64 and ARMv7 builders against fixed-buffer
handlers. ARM runs under `qemu-arm-static` with the musl cross toolchain in
`/mnt/storage/offload/toolchains`.

The Bumble GATT server is `lab/action_target.py`, the handler is
`lab/harness/action_vuln.c`.
