<div align="center">

<img src="../assets/icon.svg" width="96" height="96" alt="Brunel Research icon">

# Brunel Research

[English readme](../README.md) - [German readme](README.md)

**Bluetooth-Forschung an PaderSprinter-Busdisplays, entstanden aus einer inoffiziellen App**

Kotlin · Python · BlueZ 5.78 · Android 12+

![Android 12+](https://img.shields.io/badge/Android-12%2B-3DDC84?logo=android&logoColor=white)
![Kotlin](https://img.shields.io/badge/Kotlin-Compose-7F52FF?logo=kotlin&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

[Die App](https://github.com/janoschbl/PaderBrunel) · [Field Runbook](../docs/de/field-runbook.md) · [Exploit-Bench](../docs/de/exploit-bench.md)

</div>

---

## Warum es das gibt

Ich habe [PaderBrunel](https://github.com/janoschbl/PaderBrunel) gebaut, einen inoffiziellen Android-Client für den PaderSprinter-Fahrplan. Damit der Live-Bus-Bildschirm funktioniert, habe ich zurückentwickelt, wie die Original-App einen Bus findet und ihn nach Routentext fragt. Das führte mich zu den BLE-Modulen an den Haltestellen und in den Fahrzeugen.

Die Module antworten mit dem Namen `BlueZ 5.78`, der H&D Wireless OUI `78:C4:0E` und einer PnP-ID, die zu BlueZ passt. Sie stellen eine lesbare Routen-Charakteristik und eine beschreibbare Aktions-Charakteristik bereit. Den Aktionspfad übernimmt eine Vendor-App, nicht BlueZ. Keiner dieser Pfade verlangt eine Authentifizierung.

Ich wollte wissen, wie weit der Zugriff reicht. Aus dieser Frage entstanden eine Capture-App, ein Python-Bench, ein BlueZ-Labor, ein ESP32-Experiment, zwei Overflow-Kandidaten und jede Menge Felddaten. Dieses Repository hält die Werkzeuge, die Laborbeweise und die Notizen.

Die Forschung ist unabhängig und nicht mit PaderSprinter, dem Verkehrsverbund oder dem Modulhersteller verbunden. Nichts hier ist ein offizielles Security Advisory.

## Was ich gefunden habe

| Befund | Beleg | Status |
|---|---|---|
| Busmodule laufen mit BlueZ 5.78 auf H&D-Wireless-Hardware | Advertising-Name, GATT-Name `0x2a00`, PnP-Bytes `026b1d46024e05`, OUI | Auf mehreren Adressen bestätigt |
| Der Routen-Service `0x201f` liefert Live-Ziel und nächste Haltestelle | `0x2020`-Reads über mehrere Haltestellen | Bestätigt |
| Der Aktions-Service `0x1f1f` stellt das beschreibbare `0x1f20` bereit | GATT-Property `0x08`, Schreibvorgänge im Bus akzeptiert | Bestätigt |
| Ein 253 Byte langer ungültiger Name überläuft `name2utf8()` um drei Bytes | ASan-Absturz im Labor bei unverändertem 5.78 | DoS bei gehärteten Builds, kein Return-Overwrite |
| Ein 512-Byte-Wert für `0x1f20` erreicht einen festen Handler | Laborschreibvorgang über BlueZ 5.78, Kontrollfluss auf x86-64 und ARMv7 | Overflow im Labor bewiesen, Ziel-Offset unbekannt |
| MTU 517 wird auf dem Ziel ausgehandelt | Feldlauf und Labor | Bestätigt |
| Android verwirft numerische GATT-Status und nutzt veraltete Service-Objekte wieder | Feldlogs, reproduziert als Status 201 | Im Client behoben |
| Der EIR-Namensbug ist über Androids Advertising-API nicht erreichbar | API-Form und App-Verhalten | Bestätigt, braucht einen Linux-Host |

Die beiden Live-Kandidaten stehen unten. Keiner davon ist bisher eine bewiesene Remote-Shell auf einem Bus.

## Die Bugs

### EIR-Namensüberlauf, CVE-2026-80186

`name2utf8()` in BlueZ 5.78 kopiert bis zu 253 Bytes in `char utf8_name[250]`. Die drei zusätzlichen Bytes landen in einer Ausrichtungslücke vor dem ersten gesicherten Register, und der nicht terminierte Puffer sorgt dafür, dass die folgende Schleife Stack-Bytes liest. In einem normalen Build überlebt der Prozess. In einem gehärteten oder ASan-Build bricht er ab.

Das ist ein billiger Denial of Service. Es ist nicht der Return-Adress-Pfad. Das Labor beweist den Abbruch und das Leck mit dem exakten 5.78-Quellcode.

### Aktionsüberlauf, `0x1f20`

Die Charakteristik akzeptiert bis zu 512 Bytes. Wenn der Vendor-Handler den Wert ohne Grenze in einen festen Stack-Puffer kopiert, überschreibt der Rest die gesicherte Return-Adresse. Das Labor verwendet einen 256-Byte-Handler und bekommt `system("echo PWNED-GATT")` über einen echten 512-Byte-ATT-Write.

Die Kette ist ein normales ARMv7-ret2libc:

```text
pop {r0, r4, pc} ; <command pointer> ; filler ; system ; "cmd"
```

Der Builder hält den Befehlszeiger gerade und setzt das Thumb-Bit nur auf dem Gadget und `system`. Der Feldlauf hat noch keinen Absturz geliefert, daher sind Ziel-Offset, Canary-Zustand und Adressen weiter offen. Die Leiter ist der nächste Schritt.

## Wie die Arbeit lief

Ich begann mit dem Kartieren der Original-App und einer Feldaufzeichnung. Die Aufzeichnungen enthielten bereits den BlueZ-Namen und die Service-Map. Danach baute ich ein BlueZ-5.78-ASan-Labor, reproduzierte den EIR-Überlauf und richtete den virtuellen Pi-Bus und die Aktionsstufe ein.

Die ersten Aktionsläufe scheiterten lokal, nicht remote. Android lieferte Status 201 aus einem veralteten GATT-Cache, und die App verwarf die Nummer. Nachdem ich den Client behoben hatte, lief der komplette Laborpfad durch: MTU 517, Prepare-Writes, die Längenleiter, der End-to-End-Write und die ARMv7-Kette.

## Was heute funktioniert

- Passives und lesendes Scannen, Dekodierung von Protokoll 16 und 18 sowie RSSI-Logging.
- GATT-Enumeration, Routen-Reads und das vollständige Service-Inventar.
- Echte Fahrgast-Aktionswrites, einschließlich der `0x01`-Haltewunschanforderung.
- MTU-Aushandlung, Write Commands, Prepare Writes und Execute Write.
- Die Längenleiter, die die erste Absturzlänge ohne Firmware-Dump findet.
- Der Labor-End-to-End-Beweis und der ARMv7-Kettenbeweis unter qemu.
- Die Python- und Gradle-Tests laufen durch.

## Was noch fehlt

- Der Puffer-Offset auf dem echten Ziel. Die Leiter misst ihn.
- Ein Canary-Wert, falls der Build `-fstack-protector` nutzt.
- Die libc-Basis, `system` und ein Gadget. Dafür braucht es einen Dump, ein Leck oder Brute Force.
- Der Prozessbenutzer und das Erholungsverhalten der Vendor-App.
- Ein Zielabsturz und danach eine Ziel-Shell.

## Anfragen, die ich gesendet habe

Der Bench sendet mehr als Scans. Die Anfragespur zählt, weil jeder Pfad einen anderen Parser erreicht.

- Normale GATT-Reads auf `0x2020`, dem Device-Information-Service, GATT und der PnP-Charakteristik.
- GATT-Writes auf `0x1f20` ohne Antwort, mit Antwort, als Prepare Write und als Reliable Write.
- Längen- und Wert-Sweeps von 0 bis 512 Bytes, einschließlich des De-Bruijn-Musters.
- 255-Byte-Extended-Advertisements mit 253 ungültigen UTF-8-Namensbytes.
- Fehlerhafte ATT-, L2CAP-, SDP-, RFCOMM-, BNEP-, HIDP-, AVRCP- und BAP-Frames.
- HTTPS-Aktionsanfragen an das Produktions-Backend von ivanto. Alle beobachteten Antworten waren `{"status":false}`, ein GATT-Write-Ergebnis und eine ausgeführte Fahrzeugaktion bleiben also getrennt.

## Repository-Aufbau

| Pfad | Zweck |
|---|---|
| `capture/` | Android-Recorder, GATT-Inspektion, Presence-Sampling, Export |
| `exploit/` | Dieselbe App mit Bench, Probeliste und Aktions-UI |
| `research/` | Python-Feldclient, Protokolldekoder, Mock-Bus, Tests |
| `lab/` | BlueZ-5.78-Harnesses, btvirt, Bumble-Target, ROP-Beweise |
| `firmware/` | ESP32-S3-Buscheck-Advertiser |
| `docs/` | Pläne, Feldnotizen, Auswertungen und Belege |
| `assets/` | Repository-Icon |

## Die Android-Werkzeuge bauen

Nutze Java 21 und das Android SDK mit Plattform `android-37.0`. Setze `sdk.dir` in `local.properties`.

```sh
export JAVA_HOME=~/.local/share/mise/installs/java/temurin-21
./gradlew :capture:assembleDebug :exploit:assembleDebug
./gradlew :capture:testDebugUnitTest :exploit:testDebugUnitTest
```

Der Bench ist standardmäßig nur lesend. `Aktionen` schreibt echte Fahrgastaktionen. `Nur EIR` kann `bluetoothd` neu starten.

## Den Python-Bench ausführen

```sh
cd research
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/brunel doctor
sudo scripts/setup-radio.sh   # once, or run as root
.venv/bin/brunel scan --seconds 20
.venv/bin/brunel bench --level read
```

Für Extended Advertising ist ein BLE-5-Controller nötig. `--transport` nimmt einen Bumble-Transportstring wie `usb:0` oder `hci-socket:0`.

Die Exploit-Stufen:

```sh
.venv/bin/brunel rce --transport usb:0 --scan-seconds 25 --no-leak --dry-run
.venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --hello --write-mode command --recovery 20
.venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --ladder --write-mode prepare --recovery 25 --out ladder.json
```

Lies [den Feldlauf](../docs/de/rce-field-run-2026-11-07.md), bevor du etwas sendest. `0x01` ist eine echte Haltewunschanforderung, und ein 512-Byte-Absturz bringt das Modul zum Ausfall, bis die App neu startet.

## Labor

Das Labor läuft ohne Funkberechtigungen.

```sh
lab/scripts/action-e2e.sh
lab/scripts/action-rop.sh
lab/scripts/repro-eir.sh
```

`action-e2e.sh` startet zwei virtuelle Controller, ein Bumble-GATT-Target mit einem verwundbaren C-Handler, und sendet einen echten 512-Byte-ATT-Write. Es läuft im Command- und Prepare-Modus durch, wenn das Target `PWNED-GATT` ausgibt.

`action-rop.sh` beweist die x86-64- und ARMv7-Builder unter dem nativen Host und qemu.

## Field-Kit

- Android-Telefon mit der Capture-App.
- Raspberry Pi mit dem ASUS USB-BT500 für rohes HCI und die EIR-Stufe. Das Onboard-Pi-Funkmodul ist BLE 4.2.
- Powerbank, Notizbuch und das [Field Runbook](../docs/de/field-runbook.md).
- Optional ein ESP32-S3 für den 259-Byte-Backpack-Advertiser. Ein WROOM reicht nicht.

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [Feldlauf 2026-11-07](../docs/de/rce-field-run-2026-11-07.md) | Client-Fix, Zustellbeweis, Laufreihenfolge, Entscheidungsbaum |
| [Phase-2-Plan](../docs/de/rce-phase-2-plan-2026-11-07.md) | Hardware-Urteil, Gates, Offset- und Canary-Plan |
| [RCE-Notizen 2026-10-29](../docs/de/rce-2026-10-29.md) | Korrigiertes EIR-Ergebnis, Aktionsstufe, Ketten-Builder |
| [Exploit-Bench](../docs/de/exploit-bench.md) | Probe-Stufen, Belegschema, Grenzen |
| [Übergabe 2026-10-26](../docs/de/handover-2026-10-26.md) | Hardware-Befunde, Builds, virtueller Pi-Bus |
| [Technische Übergabe](../docs/de/security-research-handoff-2026-10-26.md) | Vollständige BLE- und GATT-Analyse, Belegstufen |
| [Buscheck-Auswertung 2026-10-28](../docs/de/buscheck-evening-evaluation-2026-10-28.md) | Routenzugang Linie 11, Messfehler |
| [Buscheck-Auswertung 2026-10-27](../docs/de/buscheck-auswertung-2026-10-27.md) | Sitzungsinventar und Fingerprint-Prüfungen |
| [Belegerfassung](../docs/de/buscheck-evidence-capture.md) | Wie man einen Laborlauf aufzeichnet |
| [Capture-Spec](../docs/de/bluetooth-capture-spec.md) | Recorder und Ereignisschema |
| [Feldtest-Checkliste](../docs/de/bluetooth-field-test.md) | Telefonvorbereitung und Aufzeichnung |
| [Bluetooth-Radar](../docs/de/bluetooth-radar.md) | Regeln für passive Beobachtung |
| [BLE-Exploitation-Plan](../docs/ble-exploitation-plan.html) | Erreichbarkeitskarte und CVE-Triage |
| [Field Runbook](../docs/de/field-runbook.md) | Kurzes Verfahren im Bus |
| [S3-Agent-Prompt](../docs/de/agent-prompt-s3.md) | Buscheck-Firmware-Brief |

## Sicherheit und Umfang

- Immer eine Verbindung zur Zeit. Fahrgäste können konkurrieren, und das Modul antwortet vielleicht mit Status 201.
- Aktionswrites ändern das Fahrgastdisplay. Sie sind harmlos, aber sichtbar.
- Ein langer Absturz bringt Bluetooth für dieses Fahrzeug zum Ausfall, bis die App neu startet. Nicht an einer Haltestelle mit Fahrgästen ausführen.
- Pairing kann eine kleine Bond-Tabelle füllen.
- Ein negatives Ergebnis ist kein Beweis für Unverwundbarkeit. Firmware unterscheidet sich je Modul.

## Lizenz

[MIT](../LICENSE). Nutze, ändere, veröffentliche oder verkaufe den Code. Behalte den Copyright-Hinweis und den Lizenztext bei.

## Disclaimer

Dies ist ein inoffizielles Forschungsprojekt. Es ist nicht mit PaderSprinter, dem Nahverkehrsverbund Paderborn/Höxter, H&D Wireless oder ivanto verbunden. Adressen und Zeitstempel stammen aus meinen eigenen Aufzeichnungen. Behandle sie als Beobachtungen, nicht als Attestierung.

Teile des Codes, der Laborskripte und der Dokumentation wurden mit KI-Unterstützung geschrieben. Ich habe alles geprüft und ausgeführt. Die Belegabschnitte sagen, was gemessen und was abgeleitet ist.
