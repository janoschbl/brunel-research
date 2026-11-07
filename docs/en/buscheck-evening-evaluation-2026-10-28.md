# Evaluation of the 27 October evening Buscheck captures

[English](buscheck-evening-evaluation-2026-10-28.md) · [Deutsch](../de/buscheck-evening-evaluation-2026-10-28.md)

## Conclusion

The captures demonstrate sustained access to live line 11 route data without
the original app. They confirm the previously observed BlueZ 5.78 fingerprint
and the expected GATT services. They do not demonstrate a target crash,
successful vehicle action, exact-name transmission, code execution, or root.

The most useful new finding is a measurement defect: the same line 11 address
briefly advertises protocol 18 without line text. My decoder then stops
updating presence even though raw packets continue arriving. At least one
reported availability gap is therefore not a radio outage at all.

This is an offline evaluation of the five supplied attachments, the
[handover](handover-2026-10-26.md), and the current local logger source.
No Bluetooth, backend, or device requests were executed for this evaluation.
The handover's earlier parser-ASan result was not rerun. Public vulnerability
identifiers and upstream patch claims were not independently checked.
The reverse-engineering skill guided the distinction between observations and
inferences. The technical-writing skill guided the report structure.
REA tools were not connected in this session, so evidence below comes from
ordinary ZIP, JSON, hashing, and source inspection, not REA Evidence records.

## The attachments contain two sessions

All times below are Europe/Berlin, UTC+1 on 27 October 2026. Event `sequence`
numbers are references into the named session's JSONL, not Markdown line numbers.

- `20261027-181517-b9e9 (1).zip` is the completed long session:
  18:15:18 to 18:34:38, 31,485 events, 7,918 advertisements, and 11 addresses.
- `20261027-181517-b9e9.zip` is a live export of the first 5,440 events of that
  same session, ending at 18:20:18.924. Those events match the completed log.
  It is not another experiment. Its session metadata still says 5,271 events,
  while its cutoff summary correctly says 5,440. That is a stale live snapshot,
  not evidence that the completed log lost those events.
- The long standalone JSONL is byte-identical to the completed ZIP's JSONL.
- `20261027-181202-e3bd.zip` and its standalone JSONL contain the same short
  session: 18:12:03 to 18:12:26, 216 events, and 116 advertisements from one address.

After deduplication there are 31,701 events and 8,034 advertisements from
12 addresses. Addresses are not independently verified physical bus identities.
Only the long session identifies line 11. The short session has no decoded line.

All three ZIP CRC checks pass. Both completed JSONL hashes match their metadata
and standalone counterparts. Event sequences are continuous. All exported
advertisement hashes match their raw bytes. These checks establish internal
consistency, not authenticity or complete radio reception.

## Line 11 data access is well supported

The main address is `78:C4:0E:C0:2B:D7`, profile `p-8eef9540`.
It appears from 18:16:41.816 to 18:33:29.144 in 7,473 scan reports.
Of these, 7,410 decode as line 11 and 63 lack line text.
RSSI ranges from −94 to −46 dBm, with a median of −57 dBm.

The long session contains 31 successful automatic GATT inventories across
five addresses and 186 successful `gatt_read` callbacks. Line 11 contributes
26 inventories and 156 of those reads. Bench results contain additional reads
outside that callback count.

Line 11 repeatedly returns name `BlueZ 5.78` and PnP bytes `026b1d46024e05`.
The service inventory includes GAP, GATT, Device Information, route service
`0x201f` with readable `0x2020`, and action service `0x1f1f` with writable
`0x1f20`. The bench inventories report five services and six readable values.
The three fingerprint and inventory results repeat the same basic layout.

Route bytes contain destination and next-stop strings separated by `0x1d`.
The destination is normally `Heinz NixdorfWendeschleife`. Next-stop observations
include the following progression:

- 18:16:45, event 414: `Langer Weg`.
- 18:17:31, bench event 1,402: `Fröbelstraße`.
- 18:19:55, event 4,872: `Gierstor`.
- 18:20:07, event 5,168: `Detmolder Tor`.
- 18:22:04, event 7,590: `Maspernplatz`.
- 18:23:49, event 9,850: `Neuhäuser Tor`.
- 18:25:58, event 12,764: `Westerntor`.
- 18:31:47, event 24,273: `Hauptbahnhof`.

This demonstrates changing operational data, not just a static device name.
Reads succeed before the recorded pairing attempt. That attempt never confirms
a new bond. The capture does not independently establish the phone's prior
bond history or the target's complete security policy.

The fingerprint is not a firmware dump. It does not identify vendor patches,
prove an unpatched parser, or establish that the bus scans incoming extended
advertisements. Bluetooth advertising and GATT serving do not by themselves
establish that the affected receive path is active.

## The active bench did not demonstrate successful actions

The long session contains three completed bench runs: one DOS-selected run
with 25 results and two READ-selected runs with 13 results each.
There are 51 probe results and nine informational findings. Those findings are
three repeated fingerprints, three inventories, and three route reads, not
nine vulnerabilities. `bench.json` preserves only the last 13-result run.

Important results in the first run are:

- Event 2,549: pairing times out after approximately 40 seconds.
- Event 2,725: known action writes report `0/4` accepted.
- Event 2,974: the action matrix reports `0/24` accepted.
- Event 3,708: the action sweep reports `0/30` accepted.
- Event 3,033: all three backend requests report HTTP 200 with `accepted=false`.
  Only the reduced status is retained, not response bodies explaining why.
  No successful backend action is established. Absence of separate
  `http_request` events does not mean no requests occurred: this bench path
  calls `BusRequests.send` directly.
- Event 3,105: all four MTU requests return 517. This is successful MTU API
  negotiation, not evidence of four different exercised wire MTUs or a bug.
- Event 3,385: the reliable-write test reports failure.
- Events 3,471, 3,502, and 3,544: all three EIR-name probes explicitly return
  `unsupported`, with `exactPayloadSent:false`.

`writeCharacteristic abgelehnt` is raised by the app when Android rejects
submission, before a successful remote write callback. These failures do not
prove that the server received and rejected the bytes or that its access
control defeated an attack. See `BenchEngine.kt:553`.

Service-Changed subscription reports success, but no Service-Changed indication
is logged. SDP and AVRCP time out. RFCOMM, BAP, BASS, BusCore, and DFU results
do not establish universal absence of those features. Their scope is the
particular discovery and connection attempts in this recording.

## No exact-name or crash experiment is established

All 8,034 saved scan records are 29, 31, or 41 bytes long, and all are marked
legacy and complete by Android. No `payload_observation` is present.
Neither ZIP contains transmitter traces, target daemon logs, or crash artifacts.
The long session has only a manual `test_stop` marker at 18:26:35.507,
event 13,466, explicitly marked `transmissionConfirmed:false`.
There is no baseline or test-start marker.

The phone's EIR probes explicitly did not transmit the required name.
These files cannot establish whether an external Pi or S3 transmitted it.
No recorded match is not proof of no transmission: this was a filtered Android
scan, not an independent raw receiver capture.

The long session records 135 evidence-gap starts and 125 recoveries across
tracked addresses. Line 11 has 36 starts and 35 recoveries. The final open gap
and gaps from passing devices are not process-crash counts.

The longest recovered line 11 inter-report interval is 13,321 ms, ending at
18:33:04.019, event 27,564. The freshness-adjusted gap is 11,821 ms.
This occurs well after the last bench ends at 18:25:41.243 and after the manual
stop marker. Ten other advertisements arrive during that interval, so it is
not a complete absence of reports from the phone. Its cause remains unknown.
The final line 11 report has RSSI −94 dBm, so the final disappearance is also
compatible with leaving reception range. Neither observation proves the cause.

The bench's three summaries contain 597, 235, and 234 samples, with 1, 0,
and 8 missing samples. The two summaries with gaps each show 252 ms downtime.
The code retains only the first missing sample and first recovery. That number
is not total downtime, precise radio downtime, or daemon restart time.
See `BenchEngine.kt:306` and `EvidenceCapture.kt:16`.

The observer itself appears stable: 4,409 long-session health samples all report
operational status, with a median interval of 258.8 ms and maximum 329.0 ms.
No dropped events, scan errors, or capture-gap events are recorded.
That supports recorder continuity, not uninterrupted reception from every bus.

## The captures reveal limits in my app

### Presence incorrectly depends on having a line

The short session's 116 reports are all protocol 18 with the expected marker
but no line text. The READ bench starts at event 44 and stops at event 143
with zero targets and zero results. No GATT reads or evidence-presence samples
are generated for that address, despite receiving its packets.

The same phenomenon occurs on line 11, not just an unfamiliar device:

- Events 5,502 to 5,600 contain 41 such reports between 18:20:22.033 and 18:20:27.084.
- Events 11,967 to 12,025 contain 22 between 18:25:27.699 and 18:25:30.131.

At event 5,605, the tracker claims a 5,216 ms inter-report interval, although
raw advertisements arrived during that interval. It measures time between
eligible decoded reports, not necessarily between radio reports.
`ExploitHub.kt:429` and `BenchEngine.kt:187` reject `decoded.ok == false` for
presence and target updates. `CaptureModel.kt:167` labels missing line text
`unknown_protocol` even when the protocol field is explicitly 18.

The other long-session no-line address, `78:C4:0E:C0:2F:73`, contributes another
138 rejected reports. There are 317 no-line decoder failures across the two
sessions. This is not evidence of 317 malformed radio packets or crashes.

The raw route characteristic also sometimes has an empty destination:
events 5,643, 12,381, and 21,359 retain a next-stop string but an empty first
field. Not every missing destination in the UI can therefore be blamed solely
on my lookup or decoder. The captures do not explain the target's reason.

### Bench summaries can call failed operations successful

All three `post_inventory` results, events 4,816, 9,804, and 12,335, say
`status:ok` and "6 readable values". All six values in each result are actually
`error: readCharacteristic abgelehnt`. `BenchEngine.kt:997` counts dictionary
entries, including errors, rather than successful reads.

Similarly, `http_actions:ok` means zero confirmations in this run, and
`att_descriptors:ok` contains a rejected descriptor read. Status labels need
per-operation interpretation, not a single green success indicator.

There is also a relevant connection-lifecycle weakness: `BenchGatt.discover()`
returns cached services before checking connectivity. Disconnect handling does
not clear that inventory. Later operations can attempt to use stale state.
This is a plausible contributor to local read and write rejections, not a
proven diagnosis of these particular failures. Bench callbacks lack the
connection and numeric submission details needed to resolve the cause.

## What the evidence supports next

The practical data-reading goal is supported. A production companion can use
the advertisement for line identity and a bounded read of `0x2020` for current
destination and next stop. The record does not establish latency, reliability,
or security guarantees for every vehicle.

The first measurement priority is to separate raw radio presence, protocol
recognition, and route availability. Replaying these logs should keep all 63
line 11 no-line packets visible, track the short session's address, and show
zero successful values in each failed final inventory. Run aggregation must
retain all 51 probe results rather than only the last 13.

The next useful experiment is a stationary passive baseline on an owned or
explicitly authorized test device, with automatic GATT reads and the bench
disabled. A separate read-only run can measure the effect of connections.
The current recording mixes scanning, repeated reads, subscriptions, pairing,
writes, and backend requests, so it is not that baseline.

On an owned test peripheral, validate reconnect handling and record numeric
Android submission results, connection state, characteristic properties, and
ATT callbacks. Add a successful fresh read before and after a test. This can
separate a broken client session from an unavailable or rejecting server.

For the security question, the missing evidence is a controlled authorized lab
comparison with identified target builds, verified transmitter and receiver
captures, and target-side daemon or crash logs. Include an untreated control
and a patched-build comparison with aligned clocks. The Pi `/crash` endpoint
tests intentional advertisement removal, not the parser vulnerability.
Further disruptive tests on operating passenger buses would not resolve these
evidence gaps safely. Firmware identity and the affected receive path remain
more important than adding more field probe attempts.

## Completed log hashes

```text
20261027-181517-b9e9  a986c108ee66a67fffedcc656cd549727ead8ccfefc8950ecef04aba6f84d017
20261027-181202-e3bd  5cf44147887b0c0c521d0f23d48281a938405242f12d79a54c0bdffade4075ba
```
