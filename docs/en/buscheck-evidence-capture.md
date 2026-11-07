# Capture a Buscheck lab run

[English](buscheck-evidence-capture.md) · [Deutsch](../de/buscheck-evidence-capture.md)

Use your own Pi virtual bus or another test device you have permission to test.
The phone records observations. It does not establish a crash or vulnerability
from advertising silence alone.

## Prepare the recording

1. Install `exploit/build/outputs/apk/debug/exploit-debug.apk`. This build is
   `1.1-buscheck-evidence`, version code 2.
2. Open Buscheck. Leave the active bench stopped.
3. For a passive baseline, turn off **Busse automatisch auslesen** before
   starting Capture. Existing GATT inspection can collect names, PnP IDs,
   services, and readable characteristics on an authorized test device, but
   connecting can change its advertising behavior. Record reads separately.
4. Start **Aufnahme starten** and grant the requested permissions. The foreground
   notification keeps the capture visible. Leave the phone near the test device.
5. Add a note identifying the test device's address, build, test case, transmitter,
   and conditions. Do not rely on an address prefix or version alone to identify
   a vulnerable build.
6. Confirm that the bus's raw advertisements appear. Press **Basis markieren**
   and record at least 30 seconds of normal behavior.

## Record the test and recovery

1. Press **Start markieren** immediately before your authorized lab test. This
   records a manual marker, not a confirmed transmission.
2. Keep recording through the event and recovery. Stay in the same position.
   A gap in the Pi virtual bus's `/crash` test validates observation and recovery
   recording only. That endpoint deliberately removes advertising and is not a
   daemon crash reproducer.
3. Press **Stopp markieren** when the external test ends, then record another
   30 seconds. Capture's main **Stopp** button ends the recording; the marker
   does not stop Capture or control a transmitter.
4. Use **Datei beifügen** while Capture still runs to attach the original
   transmitter HCI capture, target daemon logs, crash backtrace, and lab test
   results. Each attachment is limited to 16 MiB, with at most 16 per session.
   Attachment processing can delay sampling. Attach after the measurement and
   keep the original files outside the app as well.
5. Stop Capture. Choose **Export**, then **Ganze Sitzung teilen (ZIP)** or
   **ZIP in Downloads/Brunel speichern**. Prefer ZIP over the standalone JSONL
   when you need the summary and attachments.

## Check the exported evidence

1. Keep the ZIP unchanged. Verify `evidence-summary.json`'s `eventsSha256`
   against the exact `events.jsonl` bytes. This checks consistency, not who
   produced the recording. A live export has a cutoff and is not a completed run.
2. Review `captureWarnings`, `sequenceErrors`, `observer_health`, `capture_gap`,
   and `scan_error`. The summary does not claim that a warning-free scan proves
   the radio worked continuously.
3. Review `payload_observation`. Only `exact_259` identifies the complete
   required 259 bytes in an Android scan record. `name_match_other_layout`,
   `service_data_not_name`, and `incomplete_report` are not equivalent matches.
   No match does not prove that no transmission occurred.
4. Review `evidence_presence`, `evidence_gap_start`, `evidence_gap_end`, and
   `evidence_gap_invalidated`. Sampling runs nominally every 250 ms. A bus is
   considered recent for 1,500 ms after its last report. These are report gaps,
   not exact outage durations. Recovery includes both the gap estimate and
   inter-report interval. Unknown samples have `visible: null`.
5. Compare the phone's raw bytes, RSSI, PHY, SID, data-completeness status,
   scan timestamps, and receipt timestamps with the transmitter trace. Event
   sequence is write order. UTC and elapsed timestamps preserve occurrence
   time, which can differ from write order when events queue. Monotonic clocks
   from different devices cannot be compared directly.
6. Verify attachment hashes. Files under `evidence/` keep their original bytes
   with generated names. `evidence_attachment` records the original name,
   size, and SHA-256. File contents are supplied by the operator and are not
   automatically validated as crash proof.
7. To support a vulnerability finding, correlate the transmitted bytes with a
   target-side crash and backtrace on the identified build. Include the same
   authorized lab test against a patched build and a control run without the
   trigger. Document clock alignment and any timing uncertainty.

The summary always labels phone observations as
`observations_only_not_proof_of_exploitation`. Demo recordings are explicitly
`demo_not_evidence`. Android's name probes return `unsupported`; the app does
not report its service-data substitute as an exact-name reproduction.

The recorder saves raw data for bus candidates and relevant payloads. Other
received devices contribute aggregate health counters, not raw device records.
The default filter includes service UUID `0x1f1f`, manufacturer `0x7d78`, and
service data `0x1f1f`. A name-only payload without those fields requires the
unfiltered scan option. Target tracking is capped at 128 addresses per session;
an `evidence_limit` event warns if that cap is reached. The summary includes up
to 1,000 markers and 1,000 gap events. The JSONL retains the full timeline.
