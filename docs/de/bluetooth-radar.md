# Wie das Bluetooth-Bus-Radar funktioniert

[English](../en/bluetooth-radar.md) · [Deutsch](bluetooth-radar.md)

Status: Erklärung der Original-App PaderSprinter Mobil 8.7.8, keine Aussage über getestetes Fahrzeugverhalten.

Das Bus-Radar erkennt nahe Fahrzeuge und lässt Fahrgäste einen Haltewunsch, eine Einstiegshilfe oder ein Türfindungssignal auslösen. Es misst keine Entfernung wie ein physisches Radar.

Die [Capture-Seiten-Spezifikation](bluetooth-capture-spec.md) beschreibt das vorgeschlagene Debug-Feature für Brunel. Die [Feldtest-Checkliste](bluetooth-field-test.md) beschreibt den geplanten Paderborn-Besuch am 24. Oktober 2026.

## Entdeckung braucht keine Verbindung

Ein Bluetooth-Low-Energy-Modul sendet kurze Advertising-Pakete aus dem Bus. Nahe Telefone empfangen diese Pakete ohne GATT-Verbindung.

Im Systementwurf von ivanto bekommt das Modul Fahrzeugdaten vom Bordcomputer über IBIS. Das Modul sendet diese Daten aus. Es berechnet die Route nicht selbst.

Die Original-App scannt nach Advertisements, filtert auf die BusAccess-Service-Kennung `1f1f` und parst herstellerspezifische Daten. Den Parser wählt sie über die Protokollversion des Pakets.

Die App verarbeitet Scan-Ergebnisse in Ein-Sekunden-Fenstern. Sie entfernt Fahrzeuge nach fünf verpassten Fenstern oder mehr als zehn Sekunden ohne Sichtung. Die Signalstärke hilft, bestimmte doppelte Einträge aufzulösen. Sie liefert keine exakte Entfernung, Richtung oder allgemeine Einstufung der Nähe.

Ein Advertisement ist ein Broadcast, keine Antwort auf eine Fahrgastanfrage. Sein Broadcast-Intervall ist durch die statische Analyse nicht belegt.

## Kleine Kennungen werden zu lesbaren Businformationen

Die Firmendatenbank der Original-App ordnet Protokoll `16` und die Verkehrsunternehmens-ID `4` dem Wert `Padersprinter` zu. Diese Zuordnung ist ein Beleg für Unterstützung, keine Aufzeichnung aus einem echten Bus.

Die Hersteller-Payload von Version 16 enthält diese Felder:

- Service-Flags an Byte 4.
- Verkehrsunternehmens-ID an Byte 5.
- Linien-ID an Byte 6 bis 7.
- Ziel-ID an Byte 8 bis 9.
- Nächste-Haltestelle-ID an Byte 10 bis 11.
- Hardware-ID an Byte 12 bis 13.
- Kurs an Byte 14 bis 15.

Die obigen Zwei-Byte-Kennungen verwenden Little-Endian-Reihenfolge. Die Protokollversion an Byte 2 bis 3 verwendet Big-Endian-Reihenfolge. Die Offsets beziehen sich auf die Hersteller-Payload, nicht auf den vollständigen Scan-Record.

Die Original-App löst Linien-, Ziel- und Haltestellen-IDs über eine lokale Datenbank auf. Sie kann diese Nachschlagedateien über diese Routen aktualisieren:

```text
GET https://service.ivanto.de/srs/api/v1/bluetooth/updates/
GET https://service.ivanto.de/srs/api/v1/bluetooth/?filename={name}
```

Der allgemeine SRS-Client ergänzt seine Query-Parameter für Mieter und App-Identifikation. Ein Download einer Nachschlagedatei ist getrennt von der Entdeckung naher Fahrzeuge.

## Fahrgastanfragen haben zwei Zustellpfade

Für eine direkte Anfrage verbindet sich das Telefon mit der ausgewählten Bluetooth-Adresse und schreibt ein Byte in die GATT-Charakteristik `00001f20-0000-1000-8000-00805f9b34fb`.

Die Befehle sind `0x01` für einen Haltewunsch, `0x02` für Einstiegshilfe und `0x03` für das Türfindungssignal. Das sind Fahrzeugsteueranfragen, keine harmlosen Verbindungstests.

Die Original-App bietet außerdem diese HTTPS-Aktionsrouten:

```text
POST https://service.ivanto.de/busaccess/stopRequest
POST https://service.ivanto.de/busaccess/serviceRequest
POST https://service.ivanto.de/busaccess/doorsignalRequest
```

Jede Route nimmt ein JSON-Objekt mit einem Feld entgegen, `btMac`, das die Bluetooth-Adresse des ausgewählten Fahrzeugs enthält. Die Route wählt die Aktion. Der Body wählt das Fahrzeug.

Die App behandelt Bluetooth-Zustellung und Server-Zustellung als konkurrierende Pfade. Die Weiterverbindung des Servers zum Bus ist im APK nicht sichtbar. LTE, ein Broker und jede bestimmte Onboard-Schnittstelle bleiben für diesen Pfad unbewiesen.

## Abschluss ist kein Beweis für eine physische Aktion

Der Bluetooth-Pfad ist abgeschlossen, wenn der Schreibvorgang auf die Charakteristik abgeschlossen ist. Der inspizierte Pfad wartet nicht auf einen separaten Beweis, dass der Fahrer die Anfrage gesehen hat.

Das Server-Antwortmodell hat einen booleschen Wert `status`. Ein wahrer Wert schließt den Serverpfad ab. Ein falscher Wert oder ein HTTP-Fehler lässt diesen Pfad in der inspizierten Implementierung offen. So kann stattdessen der Bluetooth-Pfad abschließen.

Ein äußerer Timeout von zehn Sekunden begrenzt die kombinierte Operation. Nach Erfolg zeigt die Original-App eine Bestätigung und wendet den konfigurierten Cooldown von einer Sekunde für Anfragen an.

Das erwartete Servermodell ist keine aufgezeichnete Serverantwort. Weder ein erfolgreicher Schreibvorgang noch ein wahrer Serverstatus beweist, dass Hilfe ankam oder ein Lautsprecher Ton ausgab.

## Zusätzliche Reads sind getrennt von Steuerbefehlen

Das APK unterstützt außerdem Protokoll 18. Sein Fahrzeugdaten-Code kann die Charakteristik `00002020-0000-1000-8000-00805f9b34fb` für Ziel, Haltestellenliste und optionalen Via-Text lesen.

Die Original-Radar-Konfiguration setzt `useVehicleData=false`. Die UI nutzt diese Fahrzeugdaten-Payload in diesem Build nicht. Diese Einstellung allein beweist nicht, dass jeder frühere Read übersprungen wird.

Die separate Challenge-Response-Implementierung von `BusCoreApi` ist nicht der sichtbare BusAccess-Radar-Pfad. Das mitgelieferte MQTT-Fahrzeugkarten-Feature ist ebenfalls getrennt und in diesem Build deaktiviert.

## Protokoll 18 im Feld

Der Feldtest am 24. Oktober 2026 fand zwei Modulgenerationen. Die älteren Module (`88:6B:0F`, `00:07:80`) senden Protokoll 16. Die neueren Linux-Module (`70:B8:F6`, `78:C4:0E`, benannt `ivi` oder `ivc`) senden Protokoll 18. Die Linien 2, 5, 7, 8, 11 und 12 verwendeten Protokoll 18.

Die Hersteller-Payload von Protokoll 18 sieht für Linie 8 so aus:

```text
78 7d 00 12 13 e1 21 04 01 01 80 38 00 00 00 00 00 00
```

- Protokollversion an Byte 2 bis 3, Big-Endian, wie bei Protokoll 16.
- Ein Zähler in den unteren drei Bits von Byte 4. Er rollt von 0 bis 7, während der Bus fährt. Seine Bedeutung ist nicht bestätigt.
- Byte 5 bis 9 bleiben je Fahrzeug gleich. Sie sind nicht dekodiert.
- Byte 10 ist `0x80`, gefolgt von der Linie in ASCII und Null-Padding.

Das Advertisement hat keine Ziel- oder Nächste-Haltestelle-ID. Die Charakteristik `0x2020` im Service `0x201f` enthält beides als UTF-8-Text, getrennt durch `0x1d`:

```text
NeuenbekenHoltgrevenstraße ␝ Rathausplatz ␝
```

Das Zielfeld verbindet die Anzeigezeilen ohne Trennzeichen. Die Routen-API nennt dieselbe Richtung `Neuenbeken`, daher gleicht Brunel das Ziel nach dem Entfernen von Leerzeichen und Satzzeichen per Präfix ab.

## Warum der Bus diese Hardware hat

Der Hauptzweck ist barrierefreie Fahrgastinformation und Interaktion. Bluetooth identifiziert das tatsächlich nahe Fahrzeug, nicht nur den vom Fahrplan erwarteten Bus.

Diese Unterscheidung hilft Fahrgästen, die die Zielanzeige nicht lesen können. Einstiegshilfe-Anfragen ersparen den Griff zu einem physischen Knopf. Ein akustisches Türfindungssignal kann einem blinden Fahrgast helfen, den Einstieg zu finden.

Das APK belegt nicht, welches Hardwaremodell in welchem PaderSprinter-Bus installiert ist. Es beweist auch nicht, dass jedes Fahrzeug jede Aktion unterstützt.

## Belege und Grenzen

Die Hauptquelle ist eine statische Analyse der Original-App (Abschnitte 3.6, 5 und 8 jenes Berichts). Diese Untersuchung führte die App nicht aus, fragte keine Aktionsendpunkte ab und kommunizierte nicht mit einem echten Bus. Die Antwortbehandlung wurde zusätzlich im dekompilierten `RequestSenderManager.java` und `RequestApiResponse.java` des Pakets `de.geomobile.busaccess.api.sender` geprüft.

Plattform- und Herstellerreferenzen:

- [Android: Bluetooth Low Energy overview](https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview).
- [Android: transfer BLE data](https://developer.android.com/develop/connectivity/bluetooth/ble/transfer-ble-data).
- [ivanto system overview](https://ivanto.geomobile.de/).
- [ivantoConnect product description](https://www.ivanto.de/_Resources/Persistent/60e3ead954a8947e2af2a0b059761584e71ee568/ivantoConnect_Flyer_V1911%20%28web%29.pdf).
