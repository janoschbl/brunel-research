# Das S3-Buscheck-Gerät bauen und testen

[English](../en/README.md) · [Deutsch](README.md)

Nutze einen ESP32-S3 mit mindestens 8 MB Flash und ESP-IDF 5.x. Der Build wurde
mit ESP-IDF v5.4.3 geprüft. Ein originaler ESP32 WROOM kann dieses Projekt nicht
ausführen.

## Bauen und flashen

Aktiviere deine ESP-IDF-Umgebung und führe dann diese Befehle aus diesem
Verzeichnis aus:

```sh
idf.py set-target esp32s3
idf.py build
```

Verbinde das S3 und identifiziere seinen Port und seine Flash-Größe vor dem
Schreiben:

```sh
python -m esptool --port /dev/ttyACM0 chip_id
python -m esptool --port /dev/ttyACM0 flash_id
idf.py -p /dev/ttyACM0 flash monitor
```

Ersetze `/dev/ttyACM0` durch den tatsächlich aufgezählten Port des S3. UART0 ist
die primäre Konsole. Die sekundäre USB-Serial/JTAG-Konsole von ESP-IDF gibt Logs
auch über den nativen USB-Port des S3 aus. Beende den Monitor mit Strg+]. Führe
`erase-flash` oder das Löschen von NVS nicht als Teil der normalen Einrichtung
aus. Ein NVS-Initialisierungsfehler lässt NVS intakt und meldet den Fehler auf
der seriellen Schnittstelle.

## Buscheck nutzen

1. Verbinde dich mit `janosch` und Passwort `Jan0sch?!`. Bleib verbunden, wenn das
   Telefon warnt, dass das Netzwerk kein Internet hat.
2. Öffne `http://192.168.4.1/`.
3. Drücke **Start**. Warte auf **Running**.
4. Drücke **Stop**. Warte auf **Stopped**.

Einschalten startet immer gestoppt. Ein normaler Software-Neustart fordert Stop
an und wartet auf dessen Abschluss. Ein Stromverlust setzt den Controller zurück.
Es gibt keinen gespeicherten Laufzustand und keinen Autostart.

## HTTP- und serieller Status

`GET /` liefert die eingebettete Seite. `GET /status` gibt die folgenden Felder
zurück:

- `running`: der letzte vom Controller bestätigte Advertising-Zustand.
- `sent`: die Anzahl vom Controller bestätigter Starts seit dem Boot. Das ist
  **kein** Funkpaketzähler. Die Seite nennt es "Started sessions".
- `error`: der letzte Fehler oder eine leere Zeichenkette. Eine erfolgreiche
  Zustandsänderung löscht ihn.

`POST /start` und `POST /stop` ändern den Zustand. GET wird für beide Pfade
ebenfalls unterstützt. Den aktuellen Zustand zu wiederholen ist ein No-op. Eine
Anfrage wartet bis zu 700 ms auf den Controller. Ein Fehlschlag gibt HTTP 503 mit
demselben Status-JSON zurück. Eine abgelaufene Operation bleibt ausstehend, bis
ihr Callback eintrifft, damit ein anderer Befehl sie nicht überholen kann. Die
spätere Bestätigung des Controllers aktualisiert den Status.

Status wird jede Sekunde und nach HTTP-API-Anfragen protokolliert. Die erste
serielle Zeile enthält den Reset-Grund. Der Start protokolliert außerdem die
BLE-Adresse und die Payload-Größe. Die Seite fragt einmal pro Sekunde ab und
stellt keine externen Anfragen.

Es gibt ein Advertising-Set: Instanz 0, nicht verbindbar, nicht scannbar,
ungerichtetes Extended Advertising, 1M primäres und sekundäres PHY,
konfiguriertes Intervall 100 ms. Es gibt keine Scan Response und keinen
GATT-Server. `main/payload.h` enthält alle 259 Literalbytes. Die vollständige
Local-Name-AD-Länge ist `0xfb`, einschließlich des Typbytes `0x09` und 250
`0xff`-Bytes.

## Host-Prüfungen ausführen

Mit installiertem Node.js und C-Compiler:

```sh
node --test tests/page.test.mjs
```

Diese Prüfungen kompilieren den Literal-Payload, vergleichen jedes Byte, laufen
durch seine AD-Felder und üben die Anfragen, das Polling und die Fehleranzeige der
Seite mit gemocktem HTTP. Sie testen keinen ESP32-S3-Controller und kein
WLAN-Funkgerät.

## Funk und Telefon prüfen

Nutze für diesen Test nur den virtuellen Pi-Bus. Sein bestehender
BlueZ-5.78-Prozess und virtueller Bus können weiterlaufen. Starte sie bei Bedarf
mit den Befehlen in `docs/de/agent-prompt-s3.md`.

Das BLE-4.2-`hci0` des Pi kann das Legacy-Advertisement des virtuellen Busses
beobachten, aber die BLE-5-Extended-Daten des S3 nicht empfangen.
`btmgmt --index 0 find` kann den 259-Byte-Payload des S3 nicht beweisen. Nutze
einen anderen BLE-5-Scanner oder prüfe gleichzeitige Advertising- und
Extended-Scanning-Unterstützung auf `hci1`, bevor du diesen Adapter für beide
Rollen nutzt. Stoppe den virtuellen Bus nicht, um seinen Adapter
wiederzuverwenden, ohne zu notieren, dass der gleichzeitige Test dann unvollständig
ist.

1. Zeichne ein serielles Log und die S3-Adresse auf. Drücke **Start**.
2. Erfasse Extended-Advertising-Berichte mit einem BLE-5-Scanner und `btmon`.
   Setze Fragmente bei Bedarf zusammen. Prüfe Adresse, Complete-Data-Status,
   Länge 259, Präfix `02 01 06 03 03 1f 1f fb 09` und alle 250 letzten
   `ff`-Bytes. Eine Discovery-Liste allein prüft die Bytes nicht.
3. Öffne auf dem Telefon Buscheck und starte die Aufnahme. Bestätige, dass der
   virtuelle Bus sichtbar ist, während das S3 läuft.
4. Führe auf dem Pi `curl -X POST http://127.0.0.1:8081/crash` aus. Bestätige,
   dass die 250-ms-Samples des Telefons fehlende und wiederhergestellte Zustände
   aufzeichnen. Speichere die Telefonaufnahme.
5. Drücke **Stop**. Miss von der Anfrage bis zum letzten empfangenen S3-Bericht
   mit deaktivierter Duplikatfilterung. Bestätige, dass das Intervall unter einer
   Sekunde liegt.
6. Starte erneut, dann reboote. Bestätige, dass die Seite nach dem Boot gestoppt
   meldet und keine S3-Berichte weiterlaufen, bis ein weiterer Start erfolgt.
7. Starte erneut und lauf mindestens 10 Minuten. Halte die Seite offen und den
   seriellen Monitor aufzeichnend. Bestätige, dass es kein Boot-Banner, keinen
   Watchdog-Fehler und keinen Reset gibt.
8. Stoppe. Füge ein echtes Boardfoto, serielles Log, Funkaufnahme und
   Telefonaufnahme zu `docs/de/handover-2026-10-26.md` hinzu. Zeichne
   Host-Prüfungen nicht als Hardware-Bestandene auf.
