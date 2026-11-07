# Field runbook

[English](field-runbook.md) · [Deutsch](../de/field-runbook.md)

For a Buscheck run on a bus. Read `docs/en/handover-2026-10-26.md` first.

## Before boarding

1. Charge the phone and the Pi. Pack a power bank.
2. Install `exploit/build/outputs/apk/debug/exploit-debug.apk`
   (SHA-256: `a49f0f1b5c060969ced0b9c0610944cff78c73b917ba7458b6a3c3158e6f9027`).
3. Grant nearby-devices, location, and notification permissions.
4. Start a capture and check that advertisements arrive.
5. Start the Pi advertiser and open `http://ubuntu.local:8080/`.
6. Decide the level. `Nur lesen` is safe. `Aktionen` writes real requests.
   `Nur EIR` may restart `bluetoothd`.

## On the bus

1. Start the capture before the bus arrives. Press **Start** on the Pi page.
2. Note the stop, the visible line, and the fleet number.
3. Wait for a decoded bus profile. Do not select a simulator.
4. Start at `read` or the `Nur lesen` preset. Check the route text against the
   visible destination.
5. If the route matches, run the `Aktionen` preset or `action_known` only.
6. Run `Nur EIR` or `Alles` only on a bus you can watch. The app records the
   presence every 250 ms and shows the gap and the recovery.
7. Stop Buscheck and the Pi advertiser before leaving the bus.
8. Export the session as ZIP and copy it off the phone.

## What to record

- visible line, destination, fleet number
- address, RSSI, name, protocol
- which probes ran, which were skipped
- crash time, recovery time, whether the module came back
- whether the passenger display or announcement changed

## After the run

1. Keep the original ZIP. Do not edit it.
2. Run `brunel report` on the session.
3. Compare the crash with the lab result. A crash without a lab match is a
   candidate, not a finding.
4. Repeat on a second bus of the same build before reporting.
5. Check the backend replies separately from the radio result.

## Abort

Stop the bench and the capture if:

- the module does not come back after two minutes
- the bus leaves the stop
- the phone overheats or the battery drops fast
- a passenger action is clearly unwanted
