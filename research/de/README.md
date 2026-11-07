# Brunel-Bench

[English](../en/README.md) · [Deutsch](README.md)

Feld- und Labor-Bench für die PaderSprinter-BusAccess-BLE-Module. Sie scannt,
dekodiert Protokoll 16 und 18, liest den Routentext, zählt GATT auf, übt die
Aktions-Characteristic aus und führt die CVE-Kandidaten aus dem Research-Plan
aus.

Die Android-App `exploit/` ist dieselbe Bench mit Touch-UI. Dieses Python-Werkzeug
ist der schnelle Weg für ein Laptop und die Referenz für den Kotlin-Port.

## Installation

```sh
cd research
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/brunel doctor
```

`doctor` gibt Adapter-, `btmon`-, `vhci`- und Docker-Status aus. Ein
BLE-5-Controller ist für die Extended-Advertising-Proben erforderlich.
`--transport` akzeptiert jede Bumble-Transportzeichenkette, zum Beispiel `usb:0`
oder `hci-socket:0`.

Rohes HCI und USB brauchen Berechtigung. Führe einmal aus:

```sh
research/scripts/setup-radio.sh
```

Es setzt `cap_net_raw` auf das venv-Python und installiert eine udev-Regel für
Bluetooth-USB-Adapter. Stecke den Adapter danach neu ein. Alternativ führe den
Client mit `sudo` aus.

## Ausführen

```sh
.venv/bin/brunel scan --seconds 20
.venv/bin/brunel bench --level read
.venv/bin/brunel bench --level action --probes action_known,http_actions
.venv/bin/brunel bench --level dos --probes eir_overflow
.venv/bin/brunel bench --mock --level dos
.venv/bin/brunel chain --mock
.venv/bin/brunel report research/sessions/<id>
```

Stufen:

| Stufe | Bedeutung |
|---|---|
| `passive` | nur scannen |
| `read` | verbinden, aufzählen, lesen |
| `action` | `0x1f20` schreiben, die HTTPS-Aktionen aufrufen |
| `fuzz` | fehlerhafte ATT-, L2CAP-, SDP-, AVRCP-, A2DP-Eingaben |
| `dos` | EIR-Überlauf beim Extended Advertising |

`--mock` führt die ganze Bench gegen einen In-Process-Bus aus und ist der
schnellste Weg, eine Änderung zu prüfen. Ein Absturz im Mock ist simuliert; ein
Absturz im Feld wird aus Advertising-Stille geschlossen und mit der Ausfallzeit
aufgezeichnet.

## Belege

Sitzungen sind JSONL mit dem Schema der Aufnahme-App plus `probe_*`-, `finding`-
und `crash_*`-Ereignissen. `bench.json` enthält die Zusammenfassung.
`report.html` wird am Ende jedes Laufs erzeugt.

Ein Absturz ist kein Beweis für eine bestimmte CVE. Der Bericht hält Probe,
Payload, Stille und Wiederherstellungszeit getrennt, damit das Labor die Ursache
bestätigen kann.

## Aufbau

| Pfad | Zweck |
|---|---|
| `brunel/protocol.py` | Decoder, PDU-Builder, EIR-Payload |
| `brunel/transport.py` | Bumble-Transport |
| `brunel/mock.py` | deterministischer Testbus |
| `brunel/bench.py` | Registry, Scheduler, Crash-Watchdog |
| `brunel/probes/` | ein Modul pro Angriffsfläche |
| `tests/` | Offline-Tests |

Das Labor liegt in `../lab`.
