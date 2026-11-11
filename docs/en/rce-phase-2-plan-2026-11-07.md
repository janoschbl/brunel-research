# Phase 2 plan: from crash oracle to a shell

[English](rce-phase-2-plan-2026-11-07.md) · [Deutsch](../de/rce-phase-2-plan-2026-11-07.md)

Date: 7 November 2026
Target: `78:C4:0E:C0:2B:D7`, profile `p-8eef9540`, BlueZ 5.78
Baseline: [`rce-field-run-2026-11-07.md`](rce-field-run-2026-11-07.md)
Status: delivery is proven. The target offset, canary state, and addresses are not.

## Bottom line

The phone is enough for me to deliver the action overflow and to measure the
crash offset. It is **not** enough for the EIR name stage, and it is the weakest
of the available hosts for a ROP attempt. A Raspberry Pi with the ASUS USB-BT500,
or the laptop with the same dongle, is the correct platform for the chain. An
original ESP32 WROOM is not enough. An ESP32-S3 is optional, and only for the EIR
stage.

The missing piece is target knowledge, not hardware. Until the offset and the
address set exist, every host is only proving a crash.

## What the exploit actually does

There are two separate bugs. Do not mix them up.

### 1. Action overflow (`0x1f20`), the control-flow candidate

1. Scan for the bus advertisement and fingerprint it. The useful marker is the
   name `BlueZ 5.78` plus the service pair `0x1f1f` / `0x1f20`.
2. Connect. `0x1f20` is `PROPERTY_WRITE` and is handled by the vendor app, not
   by `bluetoothd`.
3. Negotiate MTU 517 and write a 512-byte value. This is a normal GATT write;
   it needs no pairing, no credentials, and no vendor app.
4. The vendor handler copies the value into a fixed stack buffer. If the copy is
   unbounded, the tail overwrites saved control data, including the saved return
   address.
5. I detect the overwrite remotely as advertising silence: the app process
   dies, the connection drops, and the advertisement disappears.
6. The payload is not filler by accident. `brunel rce` sends a De Bruijn pattern
   to find the offset, or an ARMv7 ret2libc chain:

   ```text
   pop {r0, r4, pc} ; <command pointer> ; filler ; system ; "cmd"
   ```

   A successful chain runs `system(cmd)` inside the vendor app.

In the lab I proved delivery and control flow, not the target. `action-e2e.sh`
sends a real 512-byte ATT write over BlueZ 5.78 to a 256-byte handler and gets
`PWNED-GATT`; `action-rop.sh` runs the same chain on x86-64 and ARMv7. On the
real target the same write is still only a **crash probe** until the offset and
addresses land.

### 2. EIR name overflow (CVE-2026-80186), the cheap DoS

A 253-byte invalid-UTF-8 local name overflows `char utf8_name[250]` by three
bytes. On stock 5.78 the three bytes land in an alignment gap and the loop stops
on a zero byte, so no return address is overwritten. A fortified or ASan build
aborts. This is a DoS, not the RCE path.

The phone cannot send this: Android's advertising API writes structured AD
fields and sends service data, not a raw `0x09` name. The Linux client and the
ESP32-S3 firmware can.

## Severity, honestly

| Property | Value |
|---|---|
| Vector | Adjacent BLE, no cable, no pairing |
| Range | Field RSSI median −57 dBm, −94 to −46 dBm; tens of metres at a stop |
| Auth | None observed; permission is server-side and still unconfirmed |
| Interaction | None on the target |
| Concurrency | One connection at a time; passengers can contend |
| Blast radius | One module, not the fleet; the bus keeps driving |
| Maturity | Lab-proven chain; remote crash oracle; no target crash yet |
| Recovery | A 512-byte crash drops Bluetooth until the app is restarted |

Approximate CVSS 3.1, with the caveat that it is an estimate:

- Remote DoS today: `AV:A/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` → about **6.5**.
- If the chain lands in a root process: `AV:A/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H`
  → about **8.4**.

It is not a worm, not Internet-scale, and not proven RCE. It is interesting
because it is unauthenticated, deterministic, and reachable from a pavement.

## What I can do with it

Today:

- read the route text, stop list, PnP ID, firmware revision, and GATT inventory;
- send real passenger actions: `0x01` stop, `0x02` entry, `0x03` door, `0x04` drive;
- crash the vendor app and take the module off Bluetooth until restart;
- fingerprint builds and compare modules.

With a landed chain:

- run commands as the app's user and learn that user with `id`;
- exfiltrate `/proc/self/maps` and dump the vendor binary and `libc`, which turns
  the next run from brute force into a clean chain;
- change the advertised name or route text as a visible beacon;
- keep a foothold, and possibly reach the HTTPS action backend and the vehicle
  interfaces the app already talks to.

Not with this chain: kernel compromise, OTA persistence, or fleet-wide spread.

## What I need to trigger it

1. Physical proximity to a vulnerable module (RSSI better than about −70 dBm).
2. A BLE 5 central with MTU 517 and a 512-byte write path.
3. The measured crash offset `L` from the ladder.
4. The canary state: `L-4` survives means a stack canary sits at `L`.
5. Addresses: `libc` base, `system`, a `pop {r0, ...}` gadget, and where the
   command string lands. These come from a dump, `/proc/self/maps`, or brute
   force.
6. The process user and the recovery behaviour after a crash.
7. Permission to change passenger-visible state, and a stop that is not imminent.

## Hardware decision

| Host | Action probe / ladder | 512-byte chain | EIR name stage | Verdict |
|---|---|---|---|---|
| Pixel 9a | Yes, with app work | Possible, lowest reliability | No | Field oracle only |
| Raspberry Pi + ASUS USB-BT500 | Yes | Yes, validated path | Yes | **Recommended** |
| Laptop + ASUS USB-BT500 | Yes | Yes | Yes | Best if carried |
| ESP32 WROOM | No (BLE 4.2) | No | No | Not enough |
| ESP32-S3 | No GATT client in firmware | No | Yes | Optional EIR beacon |

### Pixel 9a

Useful: already carries the app, BLE 5, can request MTU 517, can enumerate and
write `0x1f20`, and has the ladder and 250 ms presence measurement.

Limits:

- Android cannot send a raw 253-byte name, so the EIR stage is unavailable.
- No raw ATT PDUs and no `btmon`. Timing and opcode choice belong to Android.
- Long writes depend on the stack's prepare-write behaviour; that must be
  validated before relying on it (see the app work below).
- The app must stay in the foreground; Android can throttle or kill it.
- There is no chain probe yet: the app can send De Bruijn but cannot set
  `--offset`, `--system`, or `--gadget`.

Verdict: use it for fingerprint, hello, and the ladder if the Pi is not there.
Do not make it the primary chain host.

### Raspberry Pi

The validated path: raw HCI, exact EIR, MTU control, `btmon`, JSON output, and an
offset loop. The onboard `hci0` is BLE 4.2, so the ASUS USB-BT500 on `hci1` is
mandatory. Carry it in the backpack, tether over the phone hotspot, or drive it
over SSH. The field run commands are already in the baseline document.

Verdict: this is the host for phase 2.

### ESP32 WROOM

An original ESP32-D0WDQ6 is BLE 4.2. It cannot run the S3 Buscheck project and
cannot send the 259-byte extended advertisement. It is not a controller for this
exploit. Only reflash it as a demo target, and even then the advertisement stays
at 31 bytes.

Verdict: not needed.

### ESP32-S3

BLE 5, 259-byte extended advertisement, runs `firmware/s3-buscheck/`. That makes
it a good backpack beacon for the EIR DoS and for Pi-virtual-bus practice. It
has no GATT client, so it cannot run the action stage.

Verdict: optional, EIR only.

## What I need now

### A. App hardening before the next field run

- Add an `action_hello` probe that sends **only** `0x01`. `action_known` sends
  `0x01` to `0x04` and changes the display four times; the ladder should start from
  a one-action baseline.
- Add a structured `bench_write` event per write: numeric `status`, `props`,
  `handle`, `mtu`, `length`, first 32 bytes in hex, `op`, and `ok`. The probe
  result alone is not enough evidence.
- Make `writeLong` explicit: if the value exceeds `mtu - 3`, use
  `beginReliableWrite` / `executeReliableWrite` with `mtu - 5` chunks instead of
  assuming the Android stack will prepare-write. Keep the command path for
  values that fit.
- Add a chain probe with `offset`, `profile`, `system`, `gadget`, and `command`
  fields so the phone can run the final stage.
- Keep the 201 reconnect and cache reset. Treat two 201s as a stop condition.

### B. Bench gate

Run before touching a bus:

```sh
lab/scripts/action-e2e.sh
lab/scripts/action-rop.sh
cd research && .venv/bin/python -m pytest tests/test_rce.py
./gradlew :exploit:testDebugUnitTest :exploit:assembleDebug
```

Then install the new APK on the Pixel and run the new probe against the Pi
virtual bus. A green lab with a red field path is still a no-go.

### C. Target knowledge

- Best: a parked module or depot unit. Dump `/proc/self/maps`, the vendor app,
  and `libc`, and read the build flags and process user. This answers everything.
- Without a unit: the ladder gives `L`; the `L-4` retry distinguishes a canary;
  then brute-force the `libc` page offset with a known safe command. Expect one
  crash per miss and budget recovery time.
- Record `id` and the maps first when a chain lands.

### D. Field kit

Phone with the new APK, power bank, Pi + ASUS dongle + power, Ethernet or
hotspot tether, `btmon` capture, notebook, and the baseline runbook. Enable the
Android HCI snoop log before leaving.

## Field plan, in order

Every stage has a gate. Do not skip forward on a partial result.

| Gate | Action | Pass | Stop |
|---|---|---|---|
| 0 | Lab gate above; HCI snoop on; capture running | All green | Any red |
| 1 | Fingerprint only, `--no-leak --dry-run` or app `fingerprint` | `BlueZ 5.78`, `0x1f20` props `0x08` | Address or name changed |
| 2 | `0x01` hello, once | Write status 0, passenger display reacts | Two failures, or 201 twice |
| 3 | Ladder with prepare, from 1 upward | First `L` with advertising silence | No recovery in 60 s |
| 4 | `L-4` after recovery | Survives → canary at `L`; crashes → saved LR at `L` | Ambiguous after two tries |
| 5 | Recovery profile | `0x1f20` returns, `0x2020` still answers, downtime logged | All services gone |
| 6 | Zero-address chain at `L` | Reproducible crash at exactly `L` | Crash at another length |
| 7 | Real chain, harmless command | Command observable | Three misses |

Stage 6 is the crash reproduction, not a shell. Stage 7 is only attempted with a
full address set.

For the phone path, use `fingerprint` → `att_mtu` → `action_hello` →
`action_ladder`. For the Pi, use the exact commands in
[`rce-field-run-2026-11-07.md`](rce-field-run-2026-11-07.md). Do not run the
ladder on a bus that is about to reach the passenger stop.

## Command proof ladder

`echo` alone is invisible: the daemon's stdout is not on the air. Use an
observable effect:

1. `killall bluetoothd`: a silence clearly longer than the normal crash.
2. `hciconfig hci0 name PWNED` or `btmgmt --index 0 name PWNED`: visible in the
   next advertisement.
3. `hciconfig hci0 name "$(id)"`: small exfiltration channel.
4. `cat /proc/self/maps > /tmp/maps` then a later chain that copies it into a
   second advertisement or a network callback.

A crash plus recovery is a reachable overflow. It becomes RCE only when the
command effect is observed.

## Offsets, canary, addresses

- A crash at `L` and survival at `L-4` means a stack canary. The canary value is
  unknown; a leak or a brute force is then required.
- A crash at both `L` and `L-4` means the saved return address is at `L` and no
  canary is present. That is the easy case.
- An unaligned `L` suggests a byte-wise copy or a canary; retry `L-1`, `L-2`,
  `L-3`, `L-4` after each recovery.
- ARMv7 `system` and the gadget need the Thumb bit; the command pointer stays
  even. The builder already enforces this.
- Correction from the emulator run: on a musl build the gadget is Thumb but
  libc `system` is ARM, and `system` returns through `lr` rather than `[sp]`.
  The chain therefore loads `lr` with a `pop {r0, r4, lr}; bx r4` gadget and
  leaves `system` without the Thumb bit. See
  `docs/en/rce-emulator-2026-11-11.md`.
- If a dump is impossible, prefer a command pointer in the same buffer and a
  gadget plus `system` from a plausible `libc` mapping. One page is 4096 bytes;
  brute force that low nibble range first, not the whole address space.

## Success and evidence

Capture: the JSON/WRITE trail, the numeric statuses, the exact length at each
crash, the first 32 bytes, the downtime, the service inventory after recovery,
the advertised name after recovery, `btmon`, and an HCI snoop. A negative result
with this trail is still a result.

## Safety

- `0x01` is a real stop request. Send it once.
- A 512-byte crash drops Bluetooth until the app restarts.
- One connection at a time; passengers win.
- Restore the display state when practical.
- A negative result is not a non-vulnerability proof; firmware differs per module.

## Open questions

- Is `0x1f20` write pre-auth on the target, or does it need encryption? The hello
  stage answers this.
- Is the vendor app supervised? If it restarts by itself, recovery is quick; if
  not, a crash is a longer outage.
- Does the build use `-fstack-protector`? `L-4` answers this.
- Which user runs the vendor app? `id` after a chain.
- Is a parked module or depot unit available for a dump? That is the difference
  between a measured chain and a brute-force campaign.
