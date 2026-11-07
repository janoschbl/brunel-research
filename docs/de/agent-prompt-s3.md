# Agent-Prompt: ESP32-S3 Buscheck-Rucksack

[English](../en/agent-prompt-s3.md) · [Deutsch](agent-prompt-s3.md)

Du bist Softwareentwickler. Baue, flashe und teste ein kleines ESP32-S3-Gerät,
das ein festes Bluetooth-Advertising sendet und eine winzige Steuerseite
bereitstellt.

Nutze in der UI keine Security-Fachbegriffe. Nenne das Feature **Buscheck**.

## Liefergegenstand

Ein ESP-IDF-Projekt unter `firmware/s3-buscheck/` mit:

1. BLE-5-Extended-Advertising, nicht verbindbar, 259-Byte-Payload:
   - `02 01 06` Flags
   - `03 03 1f 1f` Service-UUID
   - `fb 09` vollständiger lokaler Name, Länge 251
   - 250 × `ff` Namensbytes
2. WLAN-Access-Point:
   - SSID `janosch`
   - Passwort `Jan0sch?!`
   - DHCP, kein Internet nötig
3. HTTP-Server auf `192.168.4.1:80`:
   - `/` Seite mit **Start** und **Stop**
   - `/start` startet das Advertising
   - `/stop` stoppt das Advertising
   - `/status` JSON mit `running`, `sent`, `error`
   - Status aktualisiert sich jede Sekunde
4. Serielles Log mit demselben Status.
5. Advertising stoppt sauber bei Stop und bei Neustart.

Die Payload ist fest. Berechne sie nicht zur Laufzeit.

## Bauen und flashen

Nutze ESP-IDF 5.x. Das Ziel ist ein ESP32-S3 mit 8 MB Flash oder mehr.

```sh
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

Wenn das Board USB-JTAG nutzt, verwende den Port, den es aufzählt. Lösche die NVS
nur, wenn das Flashen fehlschlägt.

## Gegen den Raspberry Pi testen

Der Pi betreibt einen virtuellen Bus mit dem echten BlueZ 5.78. SSH:

```text
samy@ubuntu.local
password: samy
```

Der BLE-5-Dongle ist der ASUS USB-BT500 auf `hci1`. Das Onboard-`hci0` ist BLE 4.2
und wird nur als Scanner verwendet.

Auf dem Pi:

```sh
sudo systemctl stop bluetooth
sudo pkill -x bluetoothd
sudo btmgmt --index 1 power off
sudo btmgmt --index 1 power on
sudo /home/samy/bluez-5.78/src/bluetoothd -n -d -E
sudo python3 /home/samy/pi_virtual_bus.py --adapter /org/bluez/hci1 --port 8081
```

Der virtuelle Bus sendet Advertising für Protokoll 18 Linie 8 und stellt die Routen-
und Aktions-Charakteristiken bereit. `curl -X POST http://127.0.0.1:8081/crash` entfernt
das Advertising für 5 Sekunden.

Testschritte:

1. Schalte den S3 ein. Verbinde dich mit dem WLAN `janosch` und `Jan0sch?!`.
2. Öffne `http://192.168.4.1/`.
3. Drücke **Start**.
4. Scanne auf dem Pi mit `sudo btmgmt --index 0 find` und bestätige, dass die S3-Adresse
   mit einem 259-Byte-Advertising erscheint.
5. Öffne die Buscheck-App auf dem Telefon, starte Capture und bestätige, dass der virtuelle Bus
   sichtbar ist.
6. Löse `/crash` auf dem Pi aus. Bestätige, dass die App den fehlenden Bus und die
   Erholung aufzeichnet.
7. Drücke **Stop** auf dem S3. Bestätige, dass das Advertising verschwindet.

## Abnahmekriterien

- Der S3 sendet exakt 259 Bytes, die ersten Bytes `02 01 06 03 03 1f 1f fb 09`.
- Das Telefon sieht den virtuellen Bus, während der S3 sendet.
- `/crash` erzeugt eine sichtbare Lücke in der 250-ms-Messung der App.
- Stop entfernt das Advertising innerhalb einer Sekunde.
- Der AP und die Seite funktionieren ohne Internet.
- Keine Watchdog-Resets während eines 10-Minuten-Laufs.

## Einschränkungen

- Halte die Seite klein und auf einem Telefon nutzbar.
- Keine Cloud, keine externen Anfragen.
- Ein Advertising-Set, eine feste Payload.
- Logge Fehler auf die serielle Schnittstelle und nach `/status`.
- Benenne die Payload oder die Service-UUID nicht um.
- Der Pi ist das Testziel, nicht das Feldziel.

## Übergabe

Aktualisiere `docs/de/handover-2026-10-26.md` mit dem Build-Befehl, dem Flash-Port und
dem Testergebnis. Füge dem Bericht ein Foto des Boards und die serielle Ausgabe bei.
