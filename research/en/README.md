# Brunel bench

[English](README.md) · [Deutsch](../de/README.md)

Field and lab bench for the PaderSprinter BusAccess BLE modules. It scans,
decodes protocol 16 and 18, reads the route text, enumerates GATT, exercises the
action characteristic, and runs the CVE candidates from the research plan.

The Android app `exploit/` is the same bench with a touch UI. This Python tool is
the fast path for a laptop and the reference for the Kotlin port.

## Install

```sh
cd research
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/brunel doctor
```

`doctor` prints the adapter, `btmon`, `vhci`, and Docker state. A BLE 5 controller
is required for the extended-advertising probes. `--transport` accepts any Bumble
transport string, for example `usb:0` or `hci-socket:0`.

Raw HCI and USB need permission. Run once:

```sh
research/scripts/setup-radio.sh
```

It sets `cap_net_raw` on the venv Python and installs a udev rule for Bluetooth
USB adapters. Replug the adapter afterwards. Alternatively run the client with
`sudo`.

## Run

```sh
.venv/bin/brunel scan --seconds 20
.venv/bin/brunel bench --level read
.venv/bin/brunel bench --level action --probes action_known,http_actions
.venv/bin/brunel bench --level dos --probes eir_overflow
.venv/bin/brunel bench --mock --level dos
.venv/bin/brunel chain --mock
.venv/bin/brunel report research/sessions/<id>
```

Levels:

| Level | Meaning |
|---|---|
| `passive` | scan only |
| `read` | connect, enumerate, read |
| `action` | write `0x1f20`, call the HTTPS actions |
| `fuzz` | malformed ATT, L2CAP, SDP, AVRCP, A2DP |
| `dos` | extended-advertising EIR overflow |

`--mock` runs the whole bench against an in-process bus and is the fastest way to
check a change. A crash in the mock is simulated; a crash in the field is
inferred from advertising silence and recorded with the downtime.

## Evidence

Sessions are JSONL with the capture-app schema plus `probe_*`, `finding`, and
`crash_*` events. `bench.json` holds the summary. `report.html` is generated at
the end of every run.

A crash is not proof of a specific CVE. The report keeps the probe, the payload,
the silence, and the recovery time separate so the lab can confirm the cause.

## Layout

| Path | Purpose |
|---|---|
| `brunel/protocol.py` | decoder, PDU builders, EIR payload |
| `brunel/transport.py` | Bumble transport |
| `brunel/mock.py` | deterministic test bus |
| `brunel/bench.py` | registry, scheduler, crash watchdog |
| `brunel/probes/` | one module per attack surface |
| `tests/` | offline tests |

The lab lives in `../lab`.
