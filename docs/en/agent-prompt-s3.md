# Agent prompt: ESP32-S3 Buscheck backpack

[English](agent-prompt-s3.md) · [Deutsch](../de/agent-prompt-s3.md)

You are a software developer. Build, flash, and test a small ESP32-S3 device
that sends one fixed Bluetooth advertisement and serves a tiny control page.

Do not use security jargon in the UI. Call the feature **Buscheck**.

## Deliverable

An ESP-IDF project under `firmware/s3-buscheck/` with:

1. BLE 5 extended advertising, non-connectable, 259-byte payload:
   - `02 01 06` flags
   - `03 03 1f 1f` service UUID
   - `fb 09` complete local name, length 251
   - 250 × `ff` name bytes
2. Wi-Fi access point:
   - SSID `janosch`
   - password `Jan0sch?!`
   - DHCP, no internet required
3. HTTP server on `192.168.4.1:80`:
   - `/` page with **Start** and **Stop**
   - `/start` starts advertising
   - `/stop` stops advertising
   - `/status` JSON with `running`, `sent`, `error`
   - status refreshes every second
4. Serial log with the same status.
5. Advertising stops cleanly on Stop and on reboot.

The payload is fixed. Do not compute it at runtime.

## Build and flash

Use ESP-IDF 5.x. The target is ESP32-S3 with 8 MB flash or more.

```sh
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

If the board uses USB-JTAG, use the port it enumerates. Do not erase the NVS
unless flashing fails.

## Test against the Raspberry Pi

The Pi runs a virtual bus with the real BlueZ 5.78. SSH:

```text
samy@ubuntu.local
password: samy
```

The BLE 5 dongle is the ASUS USB-BT500 on `hci1`. The onboard `hci0` is BLE 4.2
and only used as a scanner.

On the Pi:

```sh
sudo systemctl stop bluetooth
sudo pkill -x bluetoothd
sudo btmgmt --index 1 power off
sudo btmgmt --index 1 power on
sudo /home/samy/bluez-5.78/src/bluetoothd -n -d -E
sudo python3 /home/samy/pi_virtual_bus.py --adapter /org/bluez/hci1 --port 8081
```

The virtual bus advertises protocol 18 line 8 and exposes the route and action
characteristics. `curl -X POST http://127.0.0.1:8081/crash` removes the
advertisement for 5 seconds.

Test steps:

1. Power the S3. Join Wi-Fi `janosch` with `Jan0sch?!`.
2. Open `http://192.168.4.1/`.
3. Press **Start**.
4. On the Pi, scan with `sudo btmgmt --index 0 find` and confirm the S3 address
   appears with a 259-byte advertisement.
5. Open the Buscheck app on the phone, start Capture, and confirm the virtual bus
   is visible.
6. Trigger `/crash` on the Pi. Confirm the app records the bus missing and the
   recovery.
7. Press **Stop** on the S3. Confirm the advertisement disappears.

## Acceptance criteria

- The S3 advertises exactly 259 bytes, first bytes `02 01 06 03 03 1f 1f fb 09`.
- The phone sees the virtual bus while the S3 advertises.
- `/crash` produces a visible gap in the app's 250 ms measurement.
- Stop removes the advertisement within one second.
- The AP and page work without internet.
- No watchdog resets during a 10-minute run.

## Constraints

- Keep the page small and usable on a phone.
- No cloud, no external requests.
- One advertising set, one fixed payload.
- Log errors to serial and to `/status`.
- Do not rename the payload or the service UUID.
- The Pi is the test target, not the field target.

## Handover

Update `docs/en/handover-2026-10-26.md` with the build command, the flash port, and
the test result. Add a photo of the board and the serial output to the report.
