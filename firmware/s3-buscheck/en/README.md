# Build and test the S3 Buscheck device

[English](README.md) · [Deutsch](../de/README.md)

Use an ESP32-S3 with at least 8 MB flash and ESP-IDF 5.x. The build was checked
with ESP-IDF v5.4.3. An original ESP32 WROOM cannot run this project.

## Build and flash

Activate your ESP-IDF environment, then run these commands from this directory:

```sh
idf.py set-target esp32s3
idf.py build
```

Connect the S3 and identify its port and flash size before writing:

```sh
python -m esptool --port /dev/ttyACM0 chip_id
python -m esptool --port /dev/ttyACM0 flash_id
idf.py -p /dev/ttyACM0 flash monitor
```

Replace `/dev/ttyACM0` with the S3's actual enumerated port. UART0 is the primary
console. ESP-IDF's secondary USB Serial/JTAG console also outputs logs through
the S3's native USB port. Exit the monitor with Ctrl+]. Do not run `erase-flash`
or erase NVS as part of normal setup. An NVS initialization error leaves NVS
intact and reports the error on serial.

## Use Buscheck

1. Join `janosch` with password `Jan0sch?!`. Stay connected if the phone warns
   that the network has no internet.
2. Open `http://192.168.4.1/`.
3. Press **Start**. Wait for **Running**.
4. Press **Stop**. Wait for **Stopped**.

Power-on always starts stopped. A normal software reboot requests Stop and
waits for its completion. A power loss resets the controller. There is no
saved running state and no auto-start.

## HTTP and serial status

`GET /` serves the embedded page. `GET /status` returns the following fields:

- `running`: the last controller-confirmed advertising state.
- `sent`: the number of controller-confirmed starts since boot. This is **not**
  an on-air packet count. The page calls it "Started sessions".
- `error`: the last error, or an empty string. A successful state change clears it.

`POST /start` and `POST /stop` change the state. GET is also supported for both
paths. Repeating the current state is a no-op. A request waits up to 700 ms for
the controller. Failure returns HTTP 503 with the same status JSON. A timed-out
operation remains pending until its callback arrives, so another command cannot
overtake it. The controller's later confirmation updates the status.

Status is logged every second and after HTTP API requests. The first serial line
includes the reset reason. Startup also logs the BLE address and payload size.
The page polls once a second and makes no external requests.

There is one advertising set: instance 0, non-connectable, non-scannable,
undirected extended advertising, 1M primary and secondary PHY, 100 ms configured
interval. There is no scan response or GATT server. `main/payload.h` contains
all 259 literal bytes. The complete local-name AD length is `0xfb`, including
the `0x09` type byte and 250 `0xff` bytes.

## Run host checks

With Node.js and a C compiler installed:

```sh
node --test tests/page.test.mjs
```

These checks compile the literal payload, compare every byte, walk its AD fields,
and exercise the page's requests, polling, and error display with mocked HTTP.
They do not test an ESP32-S3 controller or Wi-Fi radio.

## Verify the radio and phone

Use only the Pi virtual bus for this test. Its existing BlueZ 5.78 process and
virtual bus can stay running. Start them with the commands in
`docs/en/agent-prompt-s3.md` if needed.

The Pi's BLE 4.2 `hci0` can observe the virtual bus's legacy advertisement, but
cannot receive the S3's BLE 5 extended data. `btmgmt --index 0 find` cannot prove
the S3's 259-byte payload. Use another BLE 5 scanner, or verify simultaneous
advertising and extended scanning support on `hci1` before using that adapter
for both roles. Do not stop the virtual bus to reuse its adapter without noting
that the simultaneous test is then incomplete.

1. Record a serial log and the S3 address. Press **Start**.
2. Capture extended advertising reports with a BLE 5 scanner and `btmon`.
   Reassemble fragments if needed. Check the address, complete data status,
   length 259, prefix `02 01 06 03 03 1f 1f fb 09`, and all 250 final `ff` bytes.
   A discovery listing alone does not verify the bytes.
3. On the phone, open Buscheck and start Capture. Confirm the virtual bus is
   visible while the S3 runs.
4. On the Pi, run `curl -X POST http://127.0.0.1:8081/crash`. Confirm the phone's
   250 ms samples record missing and recovered states. Save the phone capture.
5. Press **Stop**. Measure from the request to the last received S3 report with
   duplicate filtering disabled. Confirm the interval is below one second.
6. Start again, then reboot. Confirm the page reports stopped after boot and no
   S3 reports continue until another Start.
7. Start again and run for at least 10 minutes. Keep the page open and the serial
   monitor recording. Confirm there is no boot banner, watchdog error, or reset.
8. Stop. Add a real board photo, serial log, radio capture, and phone capture to
   `docs/en/handover-2026-10-26.md`. Do not record host checks as hardware passes.
