<div align="center">

<img src="assets/icon.svg" width="96" height="96" alt="Brunel Research icon">

# Brunel Research

[English readme](README.md) - [German readme](de/README.md)

**Bluetooth research on PaderSprinter bus displays, born from an unofficial app**

Kotlin · Python · BlueZ 5.78 · Android 12+

![Android 12+](https://img.shields.io/badge/Android-12%2B-3DDC84?logo=android&logoColor=white)
![Kotlin](https://img.shields.io/badge/Kotlin-Compose-7F52FF?logo=kotlin&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

[The app](https://github.com/janoschbl/PaderBrunel) · [Field runbook](docs/en/field-runbook.md) · [Exploit bench](docs/en/exploit-bench.md)

</div>

---

## Why this exists

I built [PaderBrunel](https://github.com/janoschbl/PaderBrunel), an unofficial Android client for the PaderSprinter timetable. To make the live bus screen work, I reverse engineered how the original app finds a bus and asks it for route text. That led me to the BLE modules at the stops and in the vehicles.

The modules answer with the name `BlueZ 5.78`, the H&D Wireless OUI `78:C4:0E`, and a PnP ID that matches BlueZ. They expose a readable route characteristic and a writable action characteristic. A vendor app handles the action path, not BlueZ. None of these paths asks for authentication.

I wanted to know how far the access goes. That question produced a capture app, a Python bench, a BlueZ lab, an ESP32 experiment, two overflow candidates, and a lot of field data. This repository keeps the tools, the lab proofs, and the notes.

The research is independent and unaffiliated with PaderSprinter, the transport association, or the module vendor. Nothing here is an official security advisory.

## What I found

| Finding | Evidence | Status |
|---|---|---|
| Bus modules run BlueZ 5.78 on H&D Wireless hardware | Advertising name, GATT name `0x2a00`, PnP bytes `026b1d46024e05`, OUI | Confirmed on several addresses |
| Route service `0x201f` returns live destination and next stop | `0x2020` reads over several stops | Confirmed |
| Action service `0x1f1f` exposes writable `0x1f20` | GATT property `0x08`, writes accepted on the bus | Confirmed |
| A 253-byte invalid name overflows `name2utf8()` by three bytes | Lab ASan crash on stock 5.78 | DoS on fortified builds, no return overwrite |
| A 512-byte `0x1f20` value reaches a fixed handler | Lab write over BlueZ 5.78, x86-64 and ARMv7 control flow | Overflow proven in the lab, target offset unknown |
| MTU 517 is negotiated on the target | Field run and lab | Confirmed |
| Android drops numeric GATT statuses and reused stale service objects | Field logs, reproduced as status 201 | Fixed in the client |
| The EIR name bug is not reachable from Android's advertising API | API shape and app behavior | Confirmed, needs a Linux host |

The two live candidates are below. Neither is a proven remote shell on a bus yet.

## The bugs

### EIR name overflow, CVE-2026-80186

`name2utf8()` in BlueZ 5.78 copies up to 253 bytes into `char utf8_name[250]`. The three extra bytes land in an alignment gap before the first saved register, and the unterminated buffer makes the following loop read stack bytes. On a plain build the process survives. On a fortified or ASan build it aborts.

This is a cheap denial of service. It is not the return-address path. The lab proves the abort and the leak with the exact 5.78 source.

### Action overflow, `0x1f20`

The characteristic accepts up to 512 bytes. If the vendor handler copies the value into a fixed stack buffer without a bound, the tail overwrites the saved return address. The lab uses a 256-byte handler and gets `system("echo PWNED-GATT")` over a real 512-byte ATT write.

The chain is a normal ARMv7 ret2libc:

```text
pop {r0, r4, pc} ; <command pointer> ; filler ; system ; "cmd"
```

The builder keeps the command pointer even and sets the Thumb bit only on the gadget and `system`. The field run has not delivered a crash yet, so the target offset, canary state, and addresses are still open. The ladder is the next step.

## How the work ran

I started by mapping the original app and recording a field session. The recordings already contained the BlueZ name and the service map. After that I built a BlueZ 5.78 ASan lab, reproduced the EIR overflow, and set up the Pi virtual bus and the action stage.

The first action runs failed locally, not remotely. Android returned status 201 from a stale GATT cache, and the app threw the number away. After I fixed the client, the full lab path passed: MTU 517, prepare writes, the length ladder, the end-to-end write, and the ARMv7 chain.

## What works today

- Passive and read-only scanning, protocol 16 and 18 decoding, and RSSI logging.
- GATT enumeration, route reads, and the full service inventory.
- Real passenger action writes, including the `0x01` stop request.
- MTU negotiation, write commands, prepare writes, and Execute Write.
- The length ladder, which finds the first crash length without a firmware dump.
- The lab end-to-end proof and the ARMv7 chain proof under qemu.
- The Python and Gradle tests pass.

## What is still missing

- The buffer offset on the real target. The ladder measures it.
- A canary value if the build uses `-fstack-protector`.
- The libc base, `system`, and a gadget. These need a dump, a leak, or a brute force.
- The process user and the recovery behaviour of the vendor app.
- A target crash, and after that a target shell.

## Requests I sent

The bench sends more than scans. The request trail matters because each path reaches a different parser.

- Normal GATT reads on `0x2020`, the Device Information service, GATT, and the PnP characteristic.
- GATT writes to `0x1f20` with no response, with response, as prepare write, and as reliable write.
- Length and value sweeps from 0 to 512 bytes, including the De Bruijn pattern.
- 255-byte extended advertisements with 253 invalid UTF-8 name bytes.
- Malformed ATT, L2CAP, SDP, RFCOMM, BNEP, HIDP, AVRCP, and BAP frames.
- HTTPS action requests to the production ivanto backend. All observed replies were `{"status":false}`, so a GATT write result and an executed vehicle action stay separate.

## Repository layout

| Path | Purpose |
|---|---|
| `capture/` | Android recorder, GATT inspection, presence sampling, export |
| `exploit/` | Same app with the bench, the probe list, and the action UI |
| `research/` | Python field client, protocol decoders, mock bus, tests |
| `lab/` | BlueZ 5.78 harnesses, btvirt, Bumble target, rop proofs |
| `firmware/` | ESP32-S3 Buscheck advertiser |
| `docs/` | Plans, field notes, evaluations, and evidence |
| `assets/` | Repository icon |

## Build the Android tools

Use Java 21 and the Android SDK with platform `android-37.0`. Set `sdk.dir` in `local.properties`.

```sh
export JAVA_HOME=~/.local/share/mise/installs/java/temurin-21
./gradlew :capture:assembleDebug :exploit:assembleDebug
./gradlew :capture:testDebugUnitTest :exploit:testDebugUnitTest
```

The bench defaults to read only. `Aktionen` writes real passenger actions. `Nur EIR` can restart `bluetoothd`.

## Run the Python bench

```sh
cd research
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/brunel doctor
sudo scripts/setup-radio.sh   # once, or run as root
.venv/bin/brunel scan --seconds 20
.venv/bin/brunel bench --level read
```

A BLE 5 controller is required for extended advertising. `--transport` takes a Bumble transport string such as `usb:0` or `hci-socket:0`.

The exploit stages:

```sh
.venv/bin/brunel rce --transport usb:0 --scan-seconds 25 --no-leak --dry-run
.venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --hello --write-mode command --recovery 20
.venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --ladder --write-mode prepare --recovery 25 --out ladder.json
```

Read [the field run](docs/en/rce-field-run-2026-11-07.md) before sending anything. `0x01` is a real stop request, and a 512-byte crash drops the module until the app restarts.

## Lab

The lab runs without radio permissions.

```sh
lab/scripts/action-e2e.sh
lab/scripts/action-rop.sh
lab/scripts/repro-eir.sh
```

`action-e2e.sh` starts two virtual controllers, a Bumble GATT target with a vulnerable C handler, and sends a real 512-byte ATT write. It passes in command and prepare mode when the target prints `PWNED-GATT`.

`action-rop.sh` proves the x86-64 and ARMv7 builders under the native host and qemu.

## Field kit

- Android phone with the capture app.
- Raspberry Pi with the ASUS USB-BT500 for raw HCI and the EIR stage. The onboard Pi radio is BLE 4.2.
- Power bank, notebook, and the [field runbook](docs/en/field-runbook.md).
- Optional ESP32-S3 for the 259-byte backpack advertiser. A WROOM is not enough.

## Documentation

| Document | Content |
|---|---|
| [Field run 2026-11-07](docs/en/rce-field-run-2026-11-07.md) | Client fix, delivery proof, run order, decision tree |
| [Phase 2 plan](docs/en/rce-phase-2-plan-2026-11-07.md) | Hardware verdict, gates, offset and canary plan |
| [RCE notes 2026-10-29](docs/en/rce-2026-10-29.md) | Corrected EIR result, action stage, chain builders |
| [Exploit bench](docs/en/exploit-bench.md) | Probe levels, evidence schema, limits |
| [Handover 2026-10-26](docs/en/handover-2026-10-26.md) | Hardware findings, builds, Pi virtual bus |
| [Technical handoff](docs/en/security-research-handoff-2026-10-26.md) | Full BLE and GATT analysis, evidence levels |
| [Buscheck evaluation 2026-10-28](docs/en/buscheck-evening-evaluation-2026-10-28.md) | Line 11 route access, measurement defects |
| [Buscheck evaluation 2026-10-27](docs/en/buscheck-auswertung-2026-10-27.md) | Session inventory and fingerprint checks |
| [Evidence capture](docs/en/buscheck-evidence-capture.md) | How to record a lab run |
| [Capture spec](docs/en/bluetooth-capture-spec.md) | Recorder and event schema |
| [Field test checklist](docs/en/bluetooth-field-test.md) | Phone preparation and recording |
| [Bluetooth radar](docs/en/bluetooth-radar.md) | Passive observation rules |
| [BLE exploitation plan](docs/ble-exploitation-plan.html) | Reachability map and CVE triage |
| [Field runbook](docs/en/field-runbook.md) | Short on-bus procedure |
| [S3 agent prompt](docs/en/agent-prompt-s3.md) | Buscheck firmware brief |

## Safety and scope

- One connection at a time. Passengers can contend, and the module may answer with status 201.
- Action writes change the passenger display. They are harmless but visible.
- A long crash drops Bluetooth for that vehicle until the app restarts. Do not run it at the passenger stop.
- Pairing can fill a small bond table.
- A negative result is not a non-vulnerability proof. Firmware differs per module.

## License

[MIT](LICENSE). Use, change, publish, or sell the code. Keep the copyright notice and the license text with it.

## Disclaimer

This is an unofficial research project. It is not affiliated with PaderSprinter, Nahverkehrsverbund Paderborn/Höxter, H&D Wireless, or ivanto. Addresses and timestamps come from my own recordings. Treat them as observations, not attestation.

Parts of the code, lab scripts, and documentation were written with AI assistance. I reviewed and ran everything. The evidence sections say what is measured and what is inferred.
