# Buscheck evaluation of 27 October 2026

[English](buscheck-auswertung-2026-10-27.md) · [Deutsch](../de/buscheck-auswertung-2026-10-27.md)

## Result

The captures confirm the previous BlueZ 5.78 fingerprint and readable route
data. They prove no target crash, no successful exploitation and no successful
vehicle action. The most important new findings concern decoder limits and
errors in my bench evaluation.

Basis: all 24 supplied files, the [handover](handover-2026-10-26.md), the
[technical handover](security-research-handoff-2026-10-26.md), the
[capture guide](buscheck-evidence-capture.md) and the local Kotlin code.
No radio, backend or device tests were run and no app changes were made. Public
advisory statements were not re-checked. The earlier parser lab finding comes
from the existing reports, not from these captures. The technical-writing skill
guided the separation of measurements, interpretation and evidence limits.

## Scope and file consistency

14 ZIPs and ten separate JSONL files contain ten unique sessions. For each
session the longest event state was counted once: **41,920 events, 2,198
advertising reports, 21 addresses**. Addresses are not independently confirmed
vehicle identities.

All ZIP CRC checks pass. All existing event log hashes match the respective
bytes. The sequences of the ten longest logs are gapless. All 2,198 advertising
SHA-256 values match the raw bytes. That proves consistency, not origin or
complete radio capture.

The exports `105736-187a (1).zip` and `(2).zip` contain the same complete log
with 30,261 events as the separate JSONL. The smaller export without
parentheses is a live intermediate state with 17,125 events and
`duringCapture:true`. Its metadata still names 16,864 events. That is a stale
metadata state, not a proven loss in the later log. Also the multiply exported
`104624-2a3f` and `105612-8008` are not new runs.

Times are Berlin local time, UTC+1 on 27 October. The identifier contains the
local start time. The durations refer to the first and last event.

| Session without date | Approximate duration | Events | Ads | Content |
| --- | ---: | ---: | ---: | --- |
| `104325-72e9` | 2:50 min | 1,367 | 39 | One P18 device, successful GATT read |
| `104616-6514` | 6 s | 30 | 0 | No candidate |
| `104624-2a3f` | 8:31 min | 8,628 | 876 | Seven addresses, four successful GATT inventories |
| `105457-3eed` | 1:01 min | 250 | 0 | Baseline marker; DOS selection without targets or results |
| `105544-2f84` | 9 s | 3 | 0 | Version 1.0, without new observer instrumentation |
| `105559-a49f` | 11 s | 53 | 0 | 791 reports received unfiltered, no stored bus candidate |
| `105612-8008` | 1:16 min | 1,259 | 76 | READ bench ended before completion |
| `105736-187a` | 12:56 min | 30,261 | 1,207 | Several bench starts, GATT, pairing and write attempts |
| `111238-5a2b` | 3 s | 15 | 0 | No bus candidate |
| `111420-1a9c` | 13 s | 54 | 0 | No bus candidate |

`105544-2f84` overlaps with the newer app capture. That fits a separate
recorder, but alone proves no second hardware. It must not count as an
instrumented buscheck measurement run.

## Confirmed fingerprint and route access

42 `gatt_read` events come from seven successful inspections at six addresses.
The names are each `BlueZ 5.78`, the PnP bytes each `026b1d46024e05`. That
corresponds to the already documented fingerprint. Bench results additionally
contain read values.

| Address | Session | PnP read event |
| --- | --- | ---: |
| `78:C4:0E:C0:2F:CB` | `104325-72e9` | 49 |
| `78:C4:0E:A0:40:B9` | `104624-2a3f` | 1,247 |
| `78:C4:0E:A0:44:F5` | `104624-2a3f` | 1,890 |
| `78:C4:0E:A0:43:BB` | `104624-2a3f` | 2,539 |
| `78:C4:0E:C0:2A:79` | `104624-2a3f` | 7,701 |
| `78:C4:0E:A0:46:81` | `105736-187a` | 68 and 16,958 |

At `A0:46:81` the destination remains `Lemgoer Straße`, while the next stop
changes from `Westerntor` via `Rathausplatz` to `Am Bogen`. Reference points in
`105736-187a`: events 74, 16,980 and 23,226. That confirms dynamic route data,
not a firmware dump.

Event 23,128 inventories five services including `0x201f/0x2020` and
`0x1f1f/0x1f20`. The two `finding` events 23,129 and 23,227 are
`severity:info`: service inventory and route text, not two vulnerabilities.

An earlier `route_read:skipped` with "missing: route", by contrast, follows a
failed GATT inventory. Not discovered here does not mean not present. Likewise
the unsuccessful audio, DFU and BusCore samples do not reliably prove their
absence on the target.

## Decoder limit: 833 P18 reports without line text

833 of 2,198 reports, around **37.9 %**, are stored as `unknown_protocol`,
although the decoder itself recognises `protocol:18`:

- `78:C4:0E:C0:2D:F5`: 546 reports.
- `78:C4:0E:C0:2F:73`: 270 reports.
- `78:C4:0E:C0:2F:47`: 17 reports.

The examples carry the expected identifier and the marker `0x80`, but then null
bytes instead of line text. The error text "protocol 18 without line text at
byte 10" bundles various check conditions. What is missing here is not
necessarily the marker, but the text. Normal operating state, missing IBIS data
and other variants cannot yet be distinguished with it.

`CaptureModel.kt:decodeProtocol18` sets `decoded.ok == false`. The presence
tracker in `ExploitHub` and the target selection in
`BenchEngine.onAdvertisement` only accept successfully decoded devices. The raw
data is retained, but these three addresses drop out of the availability
measurement and bench target selection. That is a relevant measurement limit of
my app, not a proven firmware error.

## Radio gaps and wrong cause attribution

The independent observer writes **224 gap starts and 204 recoveries**. Some gaps
remain open at capture end. These are not 224 crashes. The bench additionally
reports ten suspected events, three recoveries and six open gaps; one suspicion
ends without completion. Both measurement paths overlap. Their counters must
not be added.

Clear example: in `105736-187a` at **10:59:10** the purely passive probe at
`A0:44:EB` starts (event 1,966). Already at **10:59:12** the bench reports
56,325 ms of silence (event 2,017). The device was therefore missing long
before the probe. Result 2,623 nevertheless gets `status:gap`.

The longest time between two reports of this device is 137.819 seconds. RSSI
values reach about −94 dBm; other devices continue to be received in between.
Movement, range, shadowing, GATT connections and competing use are plausible,
not proven explanations. A target process or restart record is missing.

`measurement_summary` is likewise not a complete outage report: event 1,535
counts 243 samples, 70 of them missing, but names only `downtime_ms:504`. The
code stores the first gap and first recovery, not the sum of all gaps. Already
the first sample is missing. The 504 ms are neither total outage nor a reliable
crash recovery time.

## Active attempts and missing trigger proof

In `105736-187a` at **11:08:12** a pairing probe starts (event 23,408), which
runs into a timeout after about 40 seconds. At **11:09:34** `action_known`
begins (event 27,497). All four values get `writeCharacteristic abgelehnt`;
result 28,793 names `0/4 accepted`.

The last scan report for `A0:46:81` is already at **11:08:46.832**
(event 25,156), i.e. before the action attempts. The later gap therefore proves
no crash triggered by these four values. A rejected Android write operation
also confirms no radio delivery or successful check of the server-side access
rights.

There are no action `http_request` events. Three successful network operations
load the lookup database, not passenger actions. Because of GATT, SDP, pairing
and write attempts the captures are nevertheless not entirely passive.

There is no `probe_start` for the three EIR name probes and no
`payload_observation` entry. All stored scan records are 29, 31 or 41 bytes
long. None is the exact 259-byte trigger. `risk:DOS` names the selected list,
not executed probes. An external transmission can, however, not be excluded
from missing phone reports. Sender HCI trace, target protocol and attached
evidence files are completely missing.

## Problems in my bench

1. **Summary loses history.** `105736-187a` contains 28 `probe_result` and two
   informative `finding` events. The final `bench.json` contains zero results
   and zero targets. `start()` replaces the state, and the export stores only
   the last run. The complete event log therefore remains authoritative.
2. **Abort is incompletely logged.** Six bench starts face three `bench_stop`
   and one `measurement_summary`. `stop()` aborts without writing a stop entry
   itself. Open probes remain.
3. **"Passive" is not connection-free.** `runTarget()` executes
   `gatt.discover()` before the selection, even with selection `passive` only.
   This option is no guaranteed connection-free control.
4. **Fingerprint failures are partly called `ok`.** "Name unknown" stands next
   to successful name/PnP reads of the same profile. That shows an incomplete
   attempt, not a version change.
5. **Timeout texts are imprecise.** SDP names 30 s at about 15,014 ms measured
   duration, AVRCP 20 s at about 15,009 ms. Nested timeouts are labelled with
   the outer probe limit.
6. **`captureWarnings:false` evaluates no causality.** The long session fulfils
   recorder checks, but has no reliable test baseline or crash evidence. The
   only manual marker is in a session without bus data. Start/stop markers and
   attached evidence are missing everywhere.

The instrumented observer runs without logged scan errors or queue losses.
6,197 health samples have a median interval of 261 ms, maximum 326 ms. That
supports regular app sampling, not gapless reception. The long capture runs
just under 13 minutes until the user stop without a visible recorder restart.
That replaces no target watchdog test.

## Assessment against the research

The data set strengthens E1: identification and normal BLE/GATT reachability.
It delivers no vendor build, backports, kernel, the affected discovery receive
path or a target backtrace. Product-related E2-E5 statements remain open. The
older offline parser finding and these radio captures are separate evidence.
Together they still prove no radio exploitation on the product. A root or code
execution claim is not supported.

Sensible first steps are corrections of the proven evaluation errors and a
stationary, connection-free control capture on an authorised test device. For
the product report the vendor build and patch mapping are still missing, as are
correlated sender and target protocols. Further active attempts in road
operation do not replace this evidence.

## SHA-256 of the complete event logs

```text
20261027-104325-72e9  7c7d271869bbe1535882ec3e6d553b51c76c4ddd756d69d8319e152d866ff40b
20261027-104616-6514  ec0b3af67ba2b3655ea93502ccd5c1f4a06c31176d357542ab3f1d09cf6bcda7
20261027-104624-2a3f  fe529ea7079dfc03b2ae3250013075ac5777f59c4a18b876406c37de3c9e4a62
20261027-105457-3eed  43687ce84ed065fbd6938855deb7c4802a0dc6ac7f9d651d9222601c45307a47
20261027-105544-2f84  f38214cc30827555e0209b04647091c8c094dda364e1efcaae3405d9b914bc08
20261027-105559-a49f  8b0790dfa7982a8a3fa0bc153a03f90c8fc1a258f92f1d767ba070d4dd47eb58
20261027-105612-8008  5324348f20c56987629cfbf106f6837e8cfd968272ab9f34a929e67286add421
20261027-105736-187a  f396ffbdd92cbddde2144c3e8318f9381f0994423298f601858718823a4c934d
20261027-111238-5a2b  b09cbba73739a80b9814e1de1d52053f6f3f16e178abecb9ecb8b5a8e2db43c9
20261027-111420-1a9c  6da8f283e3dc8b3c473a63181c9e45544eafe0b3257d8ed224e0af012ced0063
```
