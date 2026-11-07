# Confidential technical handover: bus Bluetooth, Brunel and BlueZ check candidates

[English](security-research-handoff-2026-10-26.md) · [Deutsch](../de/security-research-handoff-2026-10-26.md)

As of: 26.10.2026 · Main recording: 24.10.2026 · Audience: manufacturer PSIRT and commissioned security researchers

This document bundles the conversation context so far, the source state present on 26.10.2026 and the re-evaluated recording `20261024-180855-ed53`. It is a stocktake and a concept for an authorized security review, not a finished vulnerability proof. It contains neither exploit code nor instructions for triggering memory errors on vehicles.

The device addresses, timestamps and backend routes contained here are intended for a confidential handover. Before a public release they should be reviewed and pseudonymized where appropriate.

## 1. Result and request

The following is established:

- Several observed BLE devices send the name `BlueZ 5.78`. For three addresses this name was additionally read successfully from the GATT characteristic `0x2a00`.
- The same three devices returned a PnP ID whose values match the BlueZ upstream default and version 5.78.
- On these devices the phone can discover services and, among other things, read destination and stop texts from a vendor-specific GATT characteristic.
- The export contains 2,111 events, including 1,846 advertising results, 25 GATT connection attempts and 46 successful characteristic reads.
- In addition it contains 15 explicitly triggered HTTPS action requests. Twelve logged responses read `{"status":false}`; three requests end client-side with a timeout. An executed vehicle action is therefore not established.

Not established are the exact manufacturer firmware state, Linux kernel, BlueZ patch state including backports, active audio profiles, discovery behavior of the module, security requirements of its characteristics and a concrete exploitable vulnerability.

**The defensible report therefore reads: "Reproducible BlueZ 5.78 fingerprint and documented BLE/GATT attack surface; please enable product-related CVE triage and controlled verification."** It does not read: "Remote code execution on the bus proven."

An old version number alone proves no vulnerability. Conversely, without proof of patch state, configuration or reachability it also does not justify a blanket all-clear. What makes sense soon is a technical mapping of the candidates to the builds actually shipped.

## 2. Background and previous exchange

According to the reporter, the company was already contacted. It is said to have explained that the firmware had not yet been updated but that the vulnerabilities were harmless. For further steps or a test device with sample firmware, concrete evidence or a worked-out check concept is expected.

The original emails are not attached to this evaluation. This summary is therefore the reporter's account, not an independently verified statement by the company.

The reporter's goal is a constructive security report without damage. So far, version fingerprints and normal app communication have been evaluated; no product-related exploit proof has been produced. A PoC request is not a documented approval for modified packets, fuzzing or disruption tests in live operation.

## 3. Evidence levels and limits of statement

| Level | Meaning | Current state |
| --- | --- | --- |
| E1 | Identification/fingerprint from normal responses | Well supported for three devices by GATT name and PnP ID; further names in advertising |
| E2 | Exact product build contains the unpatched error | Not established; manufacturer sources, binary or traceable patch list are missing |
| E3 | Necessary role, configuration and input path are reachable | Established for ordinary GATT reading, largely unknown for the CVE-specific paths |
| E4 | Reproducible memory/logic error in the matching isolated build | Not performed for the product |
| E5 | Impact proven on the isolated test device | Not performed; no proven product DoS, no proven RCE |

The logs are application logs produced by my Android app. They are not an independent device attestation, not a firmware dump, not a complete radio capture and not an HCI snoop log.

A successful GATT read proves a readable characteristic under the connection state at the time. It proves neither missing link encryption nor an authentication error. Likewise, an Android connection failure is no proof that `bluetoothd` crashed.

## 4. What I built

### 4.1 Project and modules

Working directory:

```text
/home/janosch/.t3/projects/padermodern
```

The project is called PaderBrunel/Brunel and is an unofficial Android client for PaderSprinter data. The UI uses Kotlin, Jetpack Compose and Material 3.

| Module | Purpose | Android applicationId |
| --- | --- | --- |
| `app` | Normal timetable/trip companion app with optional bus detection | `dev.padermodern` |
| `capture` | Separate BusLab/capture app for recording, GATT inventory, viewing and export | `dev.padermodern.buslab` |

In the examined source state both modules are on `versionName = "1.0"`, `versionCode = 1`, `minSdk = 31`, `targetSdk = 36` and `compileSdk = 37`. Java source compatibility is 17; the project guide names JDK 21 as the build environment. Debug/local test artifacts are not equivalent to manufacturer firmware.

Important: the working tree contains uncommitted changes and new files. The commit

```text
850f159c22a7907f09e97a6f6babef8427ba9088
```

therefore does not reproduce the state described here on its own. A source code package must also contain the changed and unversioned files. From `appVersion: 1.0` in the log it cannot be derived which source state was installed at the time.

### 4.2 Architecture and communication paths

There are three paths to keep apart:

1. **Advertising:** bus module → Android BLE scanner → decoder → bus/line display.
2. **GATT reading:** phone as GATT client → bus module as GATT server → service discovery → characteristic read → interpretation of the response.
3. **Action requests:** HTTPS requests explicitly triggered in the capture app → ivanto backend. This is not the same path as a GATT write.

The existing documentation on the original PaderSprinter mobile app 8.7.8 additionally describes a direct BLE write path for passenger requests. My capture inspection does not perform such GATT writes.

The manufacturer architecture is described in the existing project documentation with a vehicle-side data reference via IBIS. From my recording neither a concrete IBIS/CAN wiring nor vehicle control reachable over Bluetooth follows. A compromised Bluetooth module would not automatically mean compromised driving operation.

## 5. How radar/scan operation works

"Radar" here denotes the display of reachable BLE devices. It is not a distance measurement and not reliable location or vehicle authentication. RSSI depends on shadowing, antennas and the environment, among other things.

### 5.1 Normal app: trip companion

The class `PassiveBusScanner` uses Android's `BluetoothLeScanner` with a filter on the service

```text
00001f1f-0000-1000-8000-00805f9b34fb
```

and `SCAN_MODE_BALANCED`. Received scan records are structurally checked and decoded as bus advertising. Simulator advertisements are discarded. Within the running process the Bluetooth address serves as the mapping key; this scanner class itself performs no GATT operation.

The name "PassiveBusScanner" does not mean that scan requests are guaranteed never to be sent at radio level. Android scan callbacks are also not a complete BLE sniffer.

The trip companion maps observations to the selected line and to GPS/route position. It uses repeated observations, time validity and conservative plausibility checks, among other things. GPS remains the fallback path. These rules reduce misassignment but are not cryptographic proof of a bus's authenticity.

For protocol 18 observations matching the trip, `VehicleDataReader` can read additional vehicle texts:

- An active GATT read operation at the same time.
- `connectGatt` with `autoConnect = false` and LE transport.
- Service discovery and exclusively read of `0x2020` in service `0x201f`.
- In the current source state: 20 second operation timeout, regular refresh after 15 seconds, cache data at most 30 seconds old, error interval 5 seconds, forgetting of old entries after 120 seconds.
- Completion by disconnect/close, also on error or timeout.
- No GATT writes, no notification subscription and no explicit `createBond` call in this class.

Android can trigger security procedures itself or use existing bonds. The absence of an explicit pairing call therefore does not prove an unencrypted link.

### 5.2 Capture app: scan and automatic inspection

The capture app is started by the user as a session and runs via a foreground service with a visible notification and stop function. It requests Bluetooth/location permissions; the main recording additionally names the notification permission.

By default the current code uses:

- `SCAN_MODE_LOW_LATENCY` and `setLegacy(false)`.
- Two alternative scan filters: service `0x1f1f` **or** manufacturer `0x7d78`. The filters are not to be understood as a simultaneous AND condition.
- An optional unfiltered scan mode. Even then, foreign devices are not persisted in full as bus profiles; instead candidates are selected by service/manufacturer.
- Automatic GATT inspection as a stored option that is on by default. The main recording confirms automatic read-only inspection.

The current `AutoInspectPolicy` sets, among other things, a minimum RSSI of −85 dBm, a minimum spacing of 10 seconds and a refresh interval of 30 seconds. Protocol 16 is in principle inspected once per address and session; protocol 18 can be read again when the data version changes or after the refresh interval has expired. Simulators, undecodable records and devices explicitly marked non-connectable are not inspected automatically. Only one inspection runs at a time.

These details describe the current source state. The exact timers at the time cannot be guaranteed retroactively from the version name 1.0.

### 5.3 Advertising decoder

The parsers first check the length of the AD structures, service identifier and manufacturer identifier. Observed or provided for in the code are:

| Field | Meaning in the current decoder |
| --- | --- |
| Service `0x1f1f` | Marking of the BusAccess context |
| Manufacturer `0x7d78` | Real bus candidates |
| Manufacturer `0x7d79` | Simulator identifier; excluded in the normal app |
| Protocol 16 | Numeric line, destination, stop, hardware and course identifiers |
| Protocol 18 | Line label as text; further texts are read via GATT when needed |
| Low three bits of byte 4 with protocol 18 | Rolling data version 0-7, **not a firmware version** |

In the internal manufacturer data array including the company ID, the protocol bytes sit at offset 2/3. For protocol 16 the identifiers from offset 6 are read as little endian; for protocol 18 the decoder checks the marker at offset 10 and reads the text line from offset 11. This description serves to map the existing decoder, not to construct modified radio packets.

Protocol 18 fields that appear as 0 in the shared model are not automatically hardware identifiers actually transmitted. Parts of this format remain unknown. The capture app preserves raw data even for an unknown protocol.

## 6. GATT system and current read operations

All following 16-bit short forms use the base `0000xxxx-0000-1000-8000-00805f9b34fb`. The vendor-specific short forms are UUIDs observed here, not a claim of standardized meaning.

### 6.1 Services of the three more closely identified BlueZ devices observed in the recording

| Service | Characteristic | Observed properties / use |
| --- | --- | --- |
| `0x1800` Generic Access | `0x2a00` | READ; device name, here `BlueZ 5.78` |
| `0x1800` | `0x2a01`, `0x2aa6` | READ |
| `0x1801` Generic Attribute | `0x2a05` | INDICATE; descriptor `0x2902` present, not subscribed |
| `0x1801` | `0x2b29` | READ and WRITE; here only read |
| `0x180a` Device Information | `0x2a50` | READ; PnP ID |
| `0x201f` | `0x2020` | READ; destination/stop texts |
| `0x1f1f` | `0x1f20` | WRITE; not written by the capture inspection |

The protocol 16 devices with successful inventory show a smaller service scope, in particular `0x1800` and `0x1f1f`. A GATT inventory does not represent a complete BR/EDR SDP inventory.

The capture inspection connects, discovers services and sequentially reads the characteristics marked as READ; service `0x1f1f` is skipped during reading. The current code sets a 30 second timeout and then ends the connection. It records UUIDs, properties and descriptor UUIDs, but reads no descriptor values and activates no notifications/indications.

**Properties are not security permissions.** A WRITE bit does not say whether pairing, link encryption, authentication or application authentication is required. Conversely, readable public timetable data does not by itself imply a privacy or access control gap.

### 6.2 Text format of the route characteristic

`0x2020` here returns UTF-8 text with the separator U+001D. My parser treats the first field as the destination and the second as the next stop; a trailing separator is possible.

Example from event 752:

```text
Characteristic: 00002020-0000-1000-8000-00805f9b34fb
Hex:            4b61756b656e626572671d4b617373656c65722053747261c39f651d
Decoded:        Kaukenberg<U+001D>Kasseler Straße<U+001D>
```

Other combinations read are Sennelager Infanterieweg / Westerntor and Technologiepark / Westerntor. These are vehicle/route texts, not firmware contents.

### 6.3 Version queries: what already exists and what is missing

In the observed Device Information Service, `0x2a50` was offered, but not Firmware Revision `0x2a26`, Software Revision `0x2a28`, Hardware Revision `0x2a27`, Model Number `0x2a24` or Manufacturer Name `0x2a29`.

Such characteristics are not a universal mechanism for reading a Linux firmware. Which of them exist is determined by the implementation. The standard description explains their meaning but does not promise that every device offers all values. [Bluetooth SIG: Device Information Service](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/DIS_v1.2/out/en/index-en.html)

A Linux kernel, package patch level or complete root file system cannot be determined by "a few more normal GATT reads" alone if the device does not provide this data.

## 7. HTTPS action path and the original app

### 7.1 Current capture code

`capture/.../BusRequests.kt` knows these POST routes:

```text
https://service.ivanto.de/busaccess/stopRequest
https://service.ivanto.de/busaccess/doorsignalRequest
https://service.ivanto.de/busaccess/serviceRequest
```

The request builder passes a Bluetooth address as the JSON field `btMac`, uses JSON as the content type and sets `Accept: application/json`. An explicit authorization header is not contained in this builder. This is a source code observation, not proof about the entire server-side security architecture.

The current UI/hub logic requires an explicit local approval, a running recording, a current advertising observation and the matching support flag. It does not send automatically on scan. The local approval is an operating gate in my app, not a permission enforced by the server.

The HTTP implementation uses a 10 second call timeout, no automatic retries and no redirects. A response only counts as accepted with 2xx, a non-truncated body and `status:true`. Manual new requests remain possible.

A timeout means "result unknown", not "guaranteed not executed". The recording does not document the physical effect in the vehicle. A door-finding/door signal in particular is not the same as a door opening command.

### 7.2 Distinction from the original PaderSprinter mobile app

The existing file `docs/en/bluetooth-radar.md` describes an earlier static analysis of the original app 8.7.8:

- Bus detection via advertising and lookup data.
- Direct passenger requests via a short write value to `0x1f20`.
- An additional HTTPS delivery path.
- Transport completion or server status, but no independent proof of the actual vehicle effect.
- A separate `BusCoreApi` challenge-response implementation and a separate MQTT function disabled in that build.

This earlier analysis was not independently reproduced for this handover by decompiling the APK again. In particular, the separate challenge-response implementation must not be assumed without proof to protect the radar/BusAccess path. Equally, no confirmed bypass may be derived from the absence of such proof.

## 8. What is logged, how and where

### 8.1 Recording and event schema

The capture app stores JSON Lines: one JSON structure per complete line. Events contain, among other things, `schemaVersion`, `sessionId`, consecutive `sequence`, `eventId`, `type`, UTC time, `elapsedRealtimeNanos` and, where applicable, `profileId` and `operationId`.

Advertising events can contain:

- Device address, device name, RSSI, Android scan time and raw scan record bytes as hex.
- Service UUIDs, service data and manufacturer data.
- Connectable/legacy status, PHY/SID/TxPower/DataStatus details, as far as Android supplies them.
- Decoder result or decoder error, parser version and lookup mapping.
- A shortened data hash for mapping.

GATT events document connection requests, callback status, service inventory, read requests and read responses with UUID, status, bytes and length. HTTP events document method, URL, JSON body, content type, response status/body or exception. Request headers are not fully recorded in the export.

Not recorded are a complete ATT/L2CAP/HCI packet stream, controller firmware, kernel messages of the bus module, its process crashes or a proven pairing/encryption state.

### 8.2 Storage locations on Android

In the current code the authoritative location is `app.noBackupFilesDir/bluetooth-captures`, typically:

```text
/data/user/0/dev.padermodern.buslab/no_backup/bluetooth-captures/<sessionId>/
    events.jsonl
    session.json
    profiles.json
    lookups/Padersprinter.sqlite
```

The exact Android path is system-dependent. This is app-private storage. The app sets `allowBackup=false`.

In addition, the current code has:

- An optional JSONL mirror via MediaStore under `Download/Brunel/<sessionId>-events.jsonl`; on by default.
- ZIP export to Downloads on completion when the mirror is enabled.
- Shareable export files under `cacheDir/exports`; with ZIP export additionally `export.json` with the export cutoff.
- An ordered write path with a bounded queue of 4,096 entries and a periodic flush roughly every second.

`dropped = 0` means that the corresponding app counter reported no discarded scan entry. It guarantees neither complete radio reception nor that Android delivered every advertisement. Hash values secure the comparability of the bytes present, not their independent origin or a court-proof chain of evidence.

The profile identifier is derived from the session identifier and address. Since the raw addresses are also contained, the export is not anonymous.

### 8.3 Import, replay and older documentation

The current import can read earlier ZIP sessions and decode raw data again with a newer parser version. This produces derived sessions, among others with a `-p2` identifier and an origin reference. Event IDs and hash values can change as a result.

**Primary evidence remains the unchanged original ZIP.** A newly decoded session is an evaluation, not the same original data set.

The files `bluetooth-capture-spec.md` and `bluetooth-field-test.md` partly contain historical planning states. Statements such as "not yet implemented", purely passive operation, older timeout/storage paths or action endpoints ruled out across the board do not fully match today's code and the main recording. For this handover, the original recording and the specifically named source state take precedence.

## 9. Main recording and verified results

### 9.1 Primary file and integrity

Original file name:

```text
20261024-180855-ed53 (1).zip
```

Local storage location:

```text
/home/janosch/.t3/userdata/attachments/b7091dbb-86b6-4014-941e-2098a2867b82-9c950062-9395-43b6-b992-08ed169c0c8e-zip.zip
```

ZIP size: 106,199 bytes. SHA-256:

```text
42566fb65365997b8cf12c013195c7ef361c5c6fe50c67c7adfbc8fd631542a4
```

Contents under `20261024-180855-ed53/`:

| File | Uncompressed size | Purpose |
| --- | ---: | --- |
| `events.jsonl` | 1,937,497 bytes | Primary event stream |
| `session.json` | 652 bytes | Session metadata and hash values |
| `profiles.json` | 4,255 bytes | Derived device overview |
| `lookups/Padersprinter.sqlite` | 36,864 bytes | Line/destination/stop lookup used |
| `export.json` | 89 bytes | Export time and cutoff |

SHA-256 of `events.jsonl`:

```text
766d78c172d78570e74e86946f4d0f26ab713daf2b1e980ea77ceadf0f9aeb73
```

SHA-256 of the lookup snapshot:

```text
3464797e5e8c838aa95f12c6f1054c37809b4c9a9c9eb990e79a07339008cf0e
```

The archive contains no bus firmware dump, no kernel build, no manufacturer root file system, no complete Bluetooth capture and no APK.

### 9.2 Time and recording device

Metadata period: 24.10.2026, `16:08:55.413471Z` to `16:37:52.694818Z`, corresponding to approximately 18:08:55 to 18:37:52 CEST.

First event: `16:08:55.452Z`; last event: `16:37:52.689Z`. The event numbers run from 1 to 2,111. The export was created after the end of the recording with cutoff 2,111.

Recording device according to the log: Google Pixel 9a, Android SDK 37, capture app 1.0, `demo:false`. **Android SDK 37 describes the phone, not the operating system of the bus module.**

### 9.3 Event counts

| Type | Count |
| --- | ---: |
| `advertisement` | 1,846 |
| `connect_requested` | 25 |
| `connection_state` | 22 |
| `gatt_services` | 13 |
| `read_requested` | 46 |
| `gatt_read` | 46, status 0 each |
| `http_request` | 15 |
| `http_response` | 12 |
| `http_error` | 3 |
| `op_start` / `op_result` | 40 each |
| `session_start` / `session_stop` / `lookup_snapshot` | 1 each |

Of the 15 HTTPS requests, eleven concern `stopRequest` and four `doorsignalRequest`; a `serviceRequest` request is not contained in this session. All twelve logged responses have HTTP 200, `status:false` and `accepted:false`. Three requests have client-side timeout exceptions.

The 40 operation results split into 13 `ok`, 24 `error` and 3 `timeout`. Here an `error` can also represent a regular negative backend response; the categories are not a device crash indicator.

There are 74 advertising results classified as `unknown_protocol`. This is first of all a decoder limit of my app, not proof of faulty firmware or a memory error on the target.

No GATT writes are logged in this session. The capture inspection implements no such writes. Because of active GATT reads and HTTPS action requests, the session as a whole was nevertheless **not purely passive**.

### 9.4 Device inventory

The table contains eleven observed Bluetooth addresses, not eleven beyond doubt different vehicles. Without additional binding, addresses and names are not reliable identities. The line details are decoded observations, not permanent vehicle assignments.

| Address | Profile ID | Ads | Format / observed line | Version note |
| --- | --- | ---: | --- | --- |
| `00:07:80:D1:90:BA` | `p-c27f3649` | 1,347 | P16 / 2; hardware ID 835 | GATT name empty; version unknown |
| `00:07:80:D1:91:58` | `p-ad62ff2c` | 15 | P16 / 6; hardware ID 781 | GATT name empty; version unknown |
| `78:C4:0E:A0:3F:F5` | `p-377c50fb` | 17 | P18 / 1 | `BlueZ 5.78` in advertising and GATT; PnP ID matching |
| `78:C4:0E:A0:44:67` | `p-eb328fbe` | 95 | P18 / 1 | `BlueZ 5.78` in advertising and GATT; PnP ID matching |
| `78:C4:0E:A0:44:F5` | `p-aa36dbca` | 4 | P18 / 12 | `BlueZ 5.78` in advertising |
| `78:C4:0E:C0:2E:1F` | `p-cbc715bf` | 25 | P18 / 4 | `BlueZ 5.78` in advertising |
| `78:C4:0E:C0:2E:E1` | `p-b9d1bb74` | 215 | P18 / 7 | `BlueZ 5.78` in advertising and GATT; PnP ID matching |
| `78:C4:0E:C0:2F:05` | `p-2a0026ae` | 23 | P18 / 5 | `BlueZ 5.78` in advertising |
| `78:C4:0E:C0:2F:CB` | `p-9808becf` | 30 | P18 / 2 | `BlueZ 5.78` in advertising |
| `88:6B:0F:4B:C0:2C` | `p-a7aa5ab9` | 1 | P16 / P+R; hardware ID 886 | Version unknown |
| `94:E6:86:E5:10:06` | `p-0a6255ac` | 74 | P18 identifier, decoder `unknown_protocol` | Name `ivi`; version unknown |

It would be wrong to report all observed devices across the board as BlueZ 5.78 installations.

### 9.5 Concrete evidence for BlueZ 5.78

For profile `p-377c50fb`:

| Event | UTC | Characteristic | Raw value |
| --- | --- | --- | --- |
| 742 | 24.10.2026, 16:23:37.206 | `0x2a00` | `426c75655a20352e3738` → `BlueZ 5.78` |
| 750 | 24.10.2026, 16:23:37.472 | `0x2a50` | `026b1d46024e05` |
| 752 | 24.10.2026, 16:23:37.611 | `0x2020` | Destination/stop text, see section 6.2 |

Further name/PnP read pairs: events 1219/1235 and 1942/1951 for `p-eb328fbe` as well as 1450/1462 and 1869/1883 for `p-b9d1bb74`.

The PnP bytes can be classified as follows:

- Vendor ID Source `0x02`: USB ID namespace.
- Vendor `0x1d6b`: Linux Foundation.
- Product `0x0246`: BlueZ default value.
- Product Version `0x054e`: corresponds to the BlueZ formation `(major << 8) | minor` for 5 and decimal 78.

These default values are formed from `VERSION` in the public BlueZ 5.78 code. This is strong additional fingerprint support, but not a cryptographic attestation and in particular not an identification of the actual hardware manufacturer through the USB vendor ID. Values can be configured or changed. [BlueZ 5.78: initialization in src/main.c](https://github.com/bluez/bluez/blob/5.78/src/main.c)

## 10. CVE triage: what should actually be passed on

The following entries are **check candidates**, not a list of confirmed product gaps. The prioritization assesses the next gain in knowledge, not a CVSS value of the vehicle already determined.

First, the manufacturer build, backports and active roles should be clarified. After that, the device name parser and actually active kernel/BLE paths are the priority. Audio and local D-Bus topics should only be raised in priority given matching preconditions.

### 10.1 CVE-2026-80186: device name/EIR parser

**Error class:** stack overflow in `name2utf8`, `src/eir.c`; according to the advisory DoS and possible code execution during discovery.

**Relation to 5.78:** The public tag 5.78 contains the unbounded copy path. The complete function, however, has an upstream UTF-8 path. A simplified rebuild of only the copy operation therefore does not automatically prove the complete parser and certainly not a radio exploitation of the product firmware.

**Required:** the module must process foreign names via the affected receive/discovery path. That it sends `BlueZ 5.78` itself or supplies a GATT name to my phone is not enough. The advisory describes in particular Extended Inquiry Response during discovery; the fix text also mentions Advertising Reports. For a claimed BLE reachability, the concrete data feed as well as controller/kernel and packet boundaries must be proven. No blanket equating with ordinary legacy BLE advertising.

**Conceptual proof:** compare manufacturer code against the fix; instrument the permitted receive path with normal lab data; then examine the complete original parser offline with memory monitoring and compare it against a patched control build. A simplified ASan example is only a proof of the error class, not a product PoC.

**Status:** well-founded upstream code candidate; manufacturer patch and reachability open. Neither DoS nor RCE proven for these devices.

Sources: [Upstream advisory](https://github.com/bluez/bluez/security/advisories/GHSA-68h6-5qgp-3975), [Code 5.78](https://github.com/bluez/bluez/blob/5.78/src/eir.c), [Fix 381b5d0](https://github.com/bluez/bluez/commit/381b5d0d208972586282116d333865ba93b8dec2), [CVE/package mapping](https://security-tracker.debian.org/tracker/CVE-2026-80186).

### 10.2 Linux kernel: check independently of the BlueZ version

A BlueZ version does not determine a kernel version. The following candidates belong in a **conditional inventory check**, not as confirmed gaps in the findings header:

| CVE | Topic / possible impact | Product mapping still needed |
| --- | --- | --- |
| `CVE-2022-42896` | L2CAP use-after-free; the described paths concern possible code execution or memory disclosure | Kernel state, fix/backport and concrete LE/BR/EDR path |
| `CVE-2022-42895` | L2CAP memory disclosure, among others kernel pointers | Affected function, configuration and protocol preconditions |
| `CVE-2024-53144` / `CVE-2024-8805` | BR/EDR just-works confirmation logic | Whether BR/EDR pairing is offered and the kernel patch is missing |
| `CVE-2020-12351` | BleedingTooth: A2MP/L2CAP type confusion with possible RCE | Correspondingly old, unpatched kernel and reachable function |
| `CVE-2020-12352` | BleedingTooth: information leak in the kernel Bluetooth path | Kernel/function mapping |
| `CVE-2020-24490` | BleedingTooth: HCI/extended advertising memory error | Kernel, controller capability and actual receive path |

For `CVE-2022-42896`, impacts of the different functions must not be transferred across the board to the LE path. `CVE-2022-42895` is not an RCE proof on its own. The Linux CNA record for `CVE-2024-53144` explicitly references `CVE-2024-8805`; the two identifiers should not be counted as two independently proven product gaps.

Suitable first evidence would be the exact kernel build ID with patch evidence and configuration. A corrupted packet against a real vehicle is neither required for that nor planned here.

Sources: [CNA 2022-42896](https://github.com/CVEProject/cvelistV5/blob/main/cves/2022/42xxx/CVE-2022-42896.json), [Red Hat 2022-42895](https://access.redhat.com/security/cve/cve-2022-42895), [Linux CNA 2024-53144 referencing 2024-8805](https://github.com/CVEProject/cvelistV5/blob/main/cves/2024/53xxx/CVE-2024-53144.json), [Fix b25e11f](https://github.com/torvalds/linux/commit/b25e11f978b63cb7857890edb3a698599cddb10e), [Red Hat: BleedingTooth](https://access.redhat.com/security/vulnerabilities/BleedingTooth).

### 10.3 CVE-2026-80185: SDP XML via local D-Bus

**Error class:** type confusion in the SDP XML parser at `RegisterProfile(ServiceRecord)`; corresponding patterns were identified in the public 5.78 code.

**Precondition:** a local process must be allowed to make the relevant D-Bus call with its own profile data. A BLE connection or a GATT read does not automatically grant this local permission.

**Impact:** what is defensible here is local DoS for now. The further-reaching upstream title about root code execution or an adjacent LE peer must not be adopted unchecked: Red Hat states explicitly that the evidence presented proves no code execution.

**Conceptual proof:** check the D-Bus policy and local accounts/processes; examine the parser exclusively in an isolated copy of the matching build. No test registration in a running vehicle.

**Status:** local, configuration-dependent candidate, no proven remote Bluetooth attack.

Sources: [Red Hat/CNA classification](https://access.redhat.com/security/cve/cve-2026-80185), [Upstream advisory](https://github.com/bluez/bluez/security/advisories/GHSA-7mmr-gwqx-vc34), [Fix 985e643](https://github.com/bluez/bluez/commit/985e643d78b09afc81d606bc0a08581fc05b1b15).

### 10.4 Audio candidates: not derivable from the bus function

An acoustic door-finding signal proves neither A2DP nor AVRCP or LE Audio. The signal could be generated entirely locally. The observed GATT service list neither proves such profiles positively nor replaces a complete role/SDP check.

| CVE | Error / discussed impact | Indispensable precondition | Relation to the previous state |
| --- | --- | --- | --- |
| `CVE-2026-19774` | A2DP processing of remote stream endpoints; stack overflow, possible code execution | Active A2DP path and ability to pair a matching foreign peer | Suspicious `store_remote_sep`/`load_remote_sep` patterns in public tag 5.78; product role unknown |
| `CVE-2026-85218` | AVRCP player settings response; writes outside stack buffers, possible code execution | Matching AVRCP controller role, BR/EDR connection and actual query | Corresponding code also in 5.78; no proof on the product |
| `CVE-2026-75032` | AVRCP GetFolderItems length check; out-of-bounds read, DoS, possible heap information leak | AVRCP browsing and connection/interaction with a matching peer | Affected parser patterns in 5.78; product path unknown |

Conceptual proof: first confirm the role and a regular sequence with an own harmless peer; only then examine the original parser offline or in an isolated lab. A speaker that merely exists is not enough for prioritization.

Sources: [19774: description and preconditions](https://security-tracker.debian.org/tracker/CVE-2026-19774), [19774: fix 912f5ef](https://github.com/bluez/bluez/commit/912f5efb0dd9bb08e408d33371a57182c5678aef), [85218: advisory](https://github.com/bluez/bluez/security/advisories/GHSA-m2vx-pw5f-rc8v), [85218: fix b21c216](https://github.com/bluez/bluez/commit/b21c216d580cf303681bfe9eab60a5414d8b6cc0), [75032: CVE](https://security-tracker.debian.org/tracker/CVE-2026-75032), [75032: fix bd89896](https://github.com/bluez/bluez/commit/bd8989620ed6e80755f06cfdb18f5b4a3913493c), [follow-up fix 5808814](https://github.com/bluez/bluez/commit/58088149872d014684a582fdb7ad01a5180c9bc5).

### 10.5 Further LE Audio advisories without a CVE mapping established here

**GHSA-9683-2chf-hfw9: BAP/BASE parser:** The advisory describes a stack overflow while processing broadcast audio metadata. According to the report, an active BAP broadcast sink can receive corresponding inputs without pairing. Necessary, however, are exactly this profile/receive path as well as matching experimental, kernel ISO and controller support.

In the public 5.78 code, `bap_sink_get_allocation` and `bap_sink_match_allocation` contain the described insufficiently bounded copying. Advisory metadata (`<=5.76`, no patched version, low rating) and description (later states too, higher severity) contradict each other. Therefore do not simply claim "5.78 affected" or "fixed from 5.77".

Sources: [BASE advisory](https://github.com/bluez/bluez/security/advisories/GHSA-9683-2chf-hfw9), [BAP code 5.78](https://github.com/bluez/bluez/blob/5.78/src/shared/bap.c).

**GHSA-7wjj-8mrm-jhw4: BASS client parser:** The advisory describes a heap overflow while parsing foreign broadcast receive state data. The target of the described attack is a BlueZ host that itself connects as a BASS GATT client to a foreign server. That is the reverse application role compared with my phone, which reads the route from the bus GATT server. According to the advisory, the experimental BASS path must be enabled.

The conspicuous allocation/multiple entry pattern is also found in the public 5.78 code. Here too, version and severity metadata are contradictory. My recording proves neither BASS nor the necessary client role of the module.

Sources: [BASS advisory](https://github.com/bluez/bluez/security/advisories/GHSA-7wjj-8mrm-jhw4), [BASS code 5.78](https://github.com/bluez/bluez/blob/5.78/src/shared/bass.c).

For both: clarify the configuration first. Only with an active path do they become priority lab candidates. Do not invent a CVE number and do not output a public severity unchecked as a product assessment.

### 10.6 Older, profile-dependent candidates from the previous research

These entries stay in the appendix so that they are not lost. They are not additional confirmed findings:

| CVE | Profile / error class | Further procedure |
| --- | --- | --- |
| [CVE-2023-44431](https://security-tracker.debian.org/tracker/CVE-2023-44431) | AVRCP memory overflow, possible code execution after connecting to a foreign device | Check role, exact manufacturer code and fix state |
| [CVE-2023-51596](https://security-tracker.debian.org/tracker/CVE-2023-51596) | PBAP heap overflow, possible code execution | Prioritize only with an active PBAP/OBEX path |
| [CVE-2023-51580](https://security-tracker.debian.org/tracker/CVE-2023-51580) | AVRCP attribute lists, out-of-bounds read | Map active role and concrete parser |
| [CVE-2023-51589](https://security-tracker.debian.org/tracker/CVE-2023-51589) | AVRCP media elements, out-of-bounds read | Also check possible overlap with newer parser reports |
| [CVE-2023-51592](https://security-tracker.debian.org/tracker/CVE-2023-51592) | AVRCP media folders, out-of-bounds read | Do not count unchecked as an independent additional finding |
| [CVE-2023-51594](https://security-tracker.debian.org/tracker/CVE-2023-51594) | OBEX processing, out-of-bounds read | Only with a proven service and affected implementation |

The previous check includes no complete, reproducible product code comparison for each of these older entries. Open distribution tracker entries are a research pointer, not a firmware finding.

### 10.7 Hits to exclude or treat separately

| Entry | Why not report as a confirmed 5.78 product gap? |
| --- | --- |
| `CVE-2021-3588` | Upstream fix already from 5.56. In 5.78 the upstream fixed-length GATT database check must also be considered; an isolated callback without its own offset check proves no regression. |
| `CVE-2021-43400` | Old GATT use-after-free fix already in 5.62; without a manufacturer regression no tenable hit against unchanged 5.78. |
| `CVE-2023-27349` | AVRCP fix already in 5.67. |
| `CVE-2023-50229` / `CVE-2023-50230` | PBAP fixes already in 5.70. |
| `CVE-2023-45866` | HID/HIDP case; not derivable from the observed BLE route service. Only with an active HID role check the concrete fix/backport state. |
| `CVE-2026-105460` | Concerns `btmon` when parsing manipulated recordings. No normal `bluetoothd` remote path; if applicable a risk of the analysis tools. |

Sources: [SUSE 2021-3588](https://www.suse.com/security/cve/CVE-2021-3588.html), [BlueZ 5.78 GATT database](https://github.com/bluez/bluez/blob/5.78/src/gatt-database.c), [upstream GATT DB checks](https://github.com/bluez/bluez/blob/5.78/src/shared/gatt-db.c), [BlueZ CVE tracker with individual entries](https://security-tracker.debian.org/tracker/source-package/bluez).

In addition, local advertising monitor reports were discussed under [GHSA-hhgc-hfgf-8m4x](https://github.com/bluez/bluez/security/advisories/GHSA-hhgc-hfgf-8m4x) and [GHSA-rfcf-9fw3-m9qp](https://github.com/bluez/bluez/security/advisories/GHSA-rfcf-9fw3-m9qp). No defensible mapping to the product copy is available here for them. Local D-Bus monitor registration is not the same as receiving a radio advertisement.

### 10.8 Interpreting patch states correctly

Upstream versions, Debian package revisions and manufacturer firmware versions are different quantities. For example, `5.87-2`, `5.87-3` and `5.87-4` are distribution revisions; they are not BlueZ upstream releases with these names.

A blanket recommendation of "update to 5.87 and everything is fixed" would not be derivable from the candidate list. What matters are the fixes actually contained, not just a numerically higher banner. A manufacturer can backport a fix to 5.78 and keep the name.

## 11. Check areas beyond known CVEs

These points are hypotheses for an authorized product review. They have no own CVE here and are not yet findings.

### 11.1 Authorization of the action characteristic

Open is which security requirements apply to `0x1f20` and what effect an accepted request has.

A meaningful lab proof would compare a documented target rule against actual enforcement: for example whether an action defined as protected is accepted by an unauthorized test client. For that, controller/GATT security state, server decision and effect at a dummy output would have to be logged together.

A WRITE property or the publicly available original client is not enough. Stop requests can intentionally be intended for all passengers. Only a violated security boundary turns this into an authorization finding.

### 11.2 Backend object authorization and abuse protection

The client addresses the backend via `btMac`. To be clarified are, among other things, object binding, permitted use case, authentication, proximity check, replay/abuse protection and server-to-module delivery.

A BOLA/access control proof would only be meaningful if a defined permission boundary exists and an impermissible crossing is shown with test accounts and two dummy objects. Staging or manufacturer test objects are intended for that, not fleet address scanning or load tests against the production API.

The current export proves no such crossing: it contains negative responses and unknown timeout results, but no proven unauthorized execution.

### 11.3 Advertising authenticity and wrong bus assignment

The current app uses observed IDs, text, address, signal strength and route plausibility. These features are not cryptographic proof of origin on their own.

The theoretical question is whether a foreign or faulty advertisement could trigger a wrong passenger display or assignment. A safe first proof is done with local replay fixtures or an own, clearly marked simulator in an isolated environment. It initially proves a client/protocol trust finding, not the takeover of a real bus.

No imitation of real bus identities in public service and no forwarding of test actions to real vehicles.

### 11.4 Own route/GATT server and update chain

The implementation of the vendor-specific service is unknown. Open review questions are input lengths, state machines, connection drops, resource limits, process privileges, separation of Bluetooth and vehicle-side interfaces as well as signing and rollback protection of updates.

An independent error in this code would not automatically be a BlueZ CVE. Without firmware or manufacturer sources I can neither confirm it nor meaningfully exclude it. From signals such as an unknown decoder format or a timeout no memory overflow follows.

## 12. What a defensible, as-gentle-as-possible proof can look like

### 12.1 Why a "harmless proof package" does not exist in general

A version read proves a version. A normal response can also prove a behavior or an enabled function. It does not automatically prove, however, that a faulty memory boundary is reachable in the executable product.

With memory errors, merely triggering the error can already crash a service, even without shellcode or further exploitation. "I am only reading" or "I do not want to exploit anything" does not automatically make modified parser inputs harmless.

The chain of proof consists of at least three parts:

1. The concrete product build contains the unpatched error.
2. The required role and input reach this code under realistic product conditions.
3. A documented security boundary or memory safety is violated; the impact actually proven is named separately.

An upstream ASan report can be part of this chain. It does not replace proof that my manufacturer device executes the same code.

### 12.2 Proposal for the researchers: staged lab evidence

| Stage | Expected artifact | Limitation |
| --- | --- | --- |
| Inventory | Firmware/BlueZ/kernel build ID, SBOM, backports, start options | No modified radio inputs needed |
| Static mapping | Diff or traceable binary/source code mapping to the fix | A missing fix location alone says nothing about active reachability |
| Regular reachability | Trace of a normal sequence with an own test peer | No error triggering; documents only the path |
| Offline regression | Original parser of the matching build under ASan/UBSan, patched control build | Keep complete preliminary checks; no artificially simplified substitute function as product proof |
| Isolated end-to-end test | Reproduction on the approved device, separate from vehicle/production backend | Only if the question requires it and the approval covers it |
| Impact report | Actually observed DoS, information leak or authorization error | Do not output DoS as RCE, module access as vehicle control |

For kernel memory errors, corresponding kernel diagnostics and an isolated test environment are needed. For D-Bus questions the actual local privileges are decisive. For audio errors the relevant role sequence must be confirmed before the actual error proof.

A good regression test documents build ID, configuration, complete call path, expected and observed behavior, stack trace or sanitizer finding as well as the behavior after applying the fix. It needs no weaponized exploit chain.

### 12.3 Safety framework

For further active checks, at least a written scope, approved devices/firmware, permitted protocols, time windows, abort criteria and contacts should be available.

A test device with isolated or simulated vehicle outputs and without a connection to productive vehicle control would be intended. Radio range or shielding and backend targets must be controlled.

Not intended are fuzzing in live operation, crash tests on deployed modules, unknown control commands, changes to fleet parameters, production API abuse, uncontrolled repetitions or a pivot to IBIS/CAN. For this document no new requests were made to bus modules or the production backend.

## 13. What is needed from the manufacturer

For a technical answer to "affected or harmless?", the following details would help:

- Product/module type and mapping of the observed addresses to hardware/firmware states.
- Firmware build ID, release date and hash; BlueZ package/commit state including backport list.
- Linux kernel release, manufacturer patch state and relevant Bluetooth configuration.
- Bluetooth controller and controller firmware.
- Build/start options of `bluetoothd`, enabled plugins, experimental/kernel experimental options and actual process privileges.
- Supported BLE/BR/EDR roles, own discovery/scan behavior, A2DP/AVRCP/PBAP/OBEX/BAP/BASS/HID use.
- GATT security requirements and target authorization for the vendor-specific characteristics.
- Security model of the HTTPS action path, meaning of the negative responses and procedure for mapping the timeout requests.
- For each relevant CVE: affected, not affected with technical justification, fixed with patch reference or still under investigation.
- An approved test device or a matching firmware copy and an explicitly agreed lab scope.

A traceable "not affected" justification can read, for example: error code not contained, fix backported or necessary role technically disabled and not reachable in the product. A pure banner or age discussion does not replace this mapping.

## 14. Where my previous evaluations and sources are

### 14.1 Existing local reports

```text
/home/janosch/.t3/userdata/attachments/bluez-audit-b7091dbb/bluez-befunde.html
/home/janosch/.t3/userdata/attachments/bluez-audit-b7091dbb/cve-kandidaten.md
/home/janosch/.t3/userdata/attachments/bluez-audit-b7091dbb/pruefplan.md
```

The files contain the earlier log inventory, CVE candidates and a check plan. This new handover sharpens or replaces contradictory short formulations with the evidence limits described here. Earlier temporary unpack directories under `/tmp` are not permanent handover artifacts.

The absolute paths in this document point to the reporter's machine. External recipients gain no access through them; the files concerned must actually be attached or provided via an agreed secure channel.

### 14.2 Important source code files

Paths relative to the repository root:

| File | Relevance |
| --- | --- |
| `app/src/main/java/dev/padermodern/data/BusAdvertisement.kt` | Advertising and vehicle text decoder |
| `app/src/main/java/dev/padermodern/companion/PassiveBusScanner.kt` | Scan of the normal app |
| `app/src/main/java/dev/padermodern/companion/VehicleDataReader.kt` | Bounded read of `0x2020` |
| `app/src/main/java/dev/padermodern/companion/TripCompanionService.kt` | Integration in trip companion and GPS/route matching |
| `capture/src/main/java/dev/padermodern/capture/CaptureHub.kt` | Recording, GATT inspection, action approval, file management, export |
| `capture/src/main/java/dev/padermodern/capture/CaptureModel.kt` | JSONL/advertising model, decoder state, AutoInspectPolicy |
| `capture/src/main/java/dev/padermodern/capture/BusRequests.kt` | HTTPS action path and response evaluation |
| `capture/src/main/java/dev/padermodern/capture/CaptureService.kt` | Android foreground service |
| `capture/src/main/java/dev/padermodern/capture/CaptureIndex.kt` | Session/profile view and evaluation |
| `capture/src/main/java/dev/padermodern/capture/SessionImport.kt` | Import and derived re-decoding |
| `capture/src/main/java/dev/padermodern/ui/screens/CaptureScreen.kt` | Scan/session UI, lists, export |
| `capture/src/main/java/dev/padermodern/ui/screens/CaptureBusScreen.kt` | Device view and operations |
| `docs/en/bluetooth-radar.md` | Earlier analysis of the original app |
| `docs/en/bluetooth-capture-spec.md` | Capture concept with partly historical details |
| `docs/en/bluetooth-field-test.md` | Field test context and procedure description |

Existing relevant tests: `BusAdvertisementTest.kt`, `BusLogReplayTest.kt`, `CaptureModelTest.kt`, `CaptureLogReplayTest.kt` and `SessionImportTest.kt` under the respective `src/test` directories.

For this documentation task the tests were not run again. Their existence is no proof of a vulnerability in the bus module.

### 14.3 Further existing recording fixtures

Under `capture/src/main/assets/fieldtest/` are:

```text
20261024-112233-0c1a.zip
20261024-112844-dbd7.zip
20261024-113127-0851.zip
20261024-113213-7fd9.zip
```

These additional sessions are import/replay material. The concrete numbers and device findings in section 9 refer exclusively to the separately provided main recording `20261024-180855-ed53`. The four fixtures were not added to its counters and were not fully audited for content again here.

### 14.4 Existing APKs and source state hashes

On 26.10.2026 the following local debug artifacts existed:

```text
app/build/outputs/apk/debug/app-debug.apk
SHA-256: e50c7979cb50c10508891f092b5a1dce8c1e8da9aac3cbddb9ce80e8dd84776b

capture/build/outputs/apk/debug/capture-debug.apk
SHA-256: d898fa8d3e88661011a9021c16d1bdccdcc58f5460e31175646ca6c7aeb731f0
```

The file timestamps were on 24.10.2026 around 14:31 CEST. Neither the time nor the version name proves that exactly these APKs were installed during the main recording. The APKs were not rebuilt for this handover.

Selected SHA-256 values of the read working state:

```text
PassiveBusScanner.kt
c643252a17a66d1b158c96503c0a5011e990fa99595cc48d7807f0e8e60fb65a

VehicleDataReader.kt
a0067d96b5be3c1990760c2c9fcb117bccb0f2a2f45672c24cc47365ae49c737

BusAdvertisement.kt
f86c6cad3e858346f307a877f7db2bce2f64f8a1f3f26682658ef0b6ddaafc72

CaptureHub.kt
f660752e4046c584797dab5b1be1f67a4ceb810c7f31e402fd140c5ede731063

CaptureModel.kt
2f1f6bdf2277e785e5d7dcadfb16471786cee8308f217d146bb4337c835a239c

BusRequests.kt
7f1f6471d626f06da8e5f5831dde186647cbb349446c5c60fa67069f92c417ff
```

This selection is not a complete source manifest. Before handing over a source code package, its own hash should be recorded together with the commit, working tree changes and build instructions. Private credentials, signing keys, personal data and files not belonging to the review do not belong in the package unchecked.

## 15. Reproducing the evaluation without radio or backend access

The following examples only read the existing local ZIP file. Prerequisites are `unzip`, `jq` and `sha256sum`. `archive` may need to be adjusted to the actual local path.

```bash
archive='/home/janosch/.t3/userdata/attachments/b7091dbb-86b6-4014-941e-2098a2867b82-9c950062-9395-43b6-b992-08ed169c0c8e-zip.zip'

sha256sum "$archive"

unzip -l "$archive"

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  sha256sum

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  jq -s 'group_by(.type) | map({type: .[0].type, count: length})'

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  jq -c 'select(.sequence == 742 or .sequence == 750 or .sequence == 752)'

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  jq -c 'select(.type == "http_response" or .type == "http_error")'
```

In the actual JSON the event identifier mentioned is called `sequence`, not `seq`.

For a separate local build or unit test, the project names Gradle tasks such as:

```bash
./gradlew :app:assembleDebug :capture:assembleDebug
./gradlew :app:testDebugUnitTest :capture:testDebugUnitTest
```

These commands were not run when this handover was created. A build can download dependencies; it does not automatically contact bus modules thereby. Existing scripts that check backend endpoints are not part of the read-only log evaluation proposed here.

## 16. Recommended handover package and key statement for the email

Suitable for the confidential handover are:

- This Markdown document.
- The unchanged original ZIP with the SHA-256 named.
- The three previous evaluation files from section 14.1 as supplementary context.
- On request, a cleaned snapshot of the actual working state including unversioned files and tests.
- If available: original correspondence, exact hardware mapping and a written test approval. These are not yet attached to the present technical evaluation.

Substantive key statement:

> I have documented a BlueZ 5.78 fingerprint supported by device name and PnP ID as well as the associated BLE/GATT communication. At present I do not claim an exploitable vulnerability of the concrete firmware. The attached candidates need a mapping to your build, your backports and the active roles. Please enable a technical review or justify non-affectedness for each relevant candidate. An isolated test device with matching firmware would enable a controlled proof without endangering deployed vehicles or the production backend.

## 17. Origin and processing limits of this handover

The compilation was created with AI support by Codex; an additional delegated AI source check was used for the CVE classification. The basis was local source code files, the original ZIP, existing project reports and linked upstream/CNA/manufacturer/distribution sources. AI support and a public advisory entry do not replace human product validation.

For this handover, local files and logs were read and public sources cross-checked. No new exploits were created, no additional radio or production API tests were performed, no firmware was extracted from a bus and no email was sent. The CVE list is a traceable triage of the previous research context, not a guarantee of a complete vulnerability inventory of all unknown firmware components.
