# Buscheck-Auswertung vom 27. Oktober 2026

[English](../en/buscheck-auswertung-2026-10-27.md) · [Deutsch](buscheck-auswertung-2026-10-27.md)

## Ergebnis

Die Aufnahmen bestätigen den bisherigen BlueZ-5.78-Fingerprint und lesbare
Routendaten. Sie belegen keinen Zielabsturz, keine erfolgreiche Ausnutzung und
keine erfolgreiche Fahrzeugaktion. Die wichtigsten neuen Befunde betreffen
Decodergrenzen und Fehler in meiner Bench-Auswertung.

Grundlagen: alle 24 bereitgestellten Dateien, der
[Handover](handover-2026-10-26.md), die
[technische Übergabe](security-research-handoff-2026-10-26.md), die
[Erfassungsanleitung](buscheck-evidence-capture.md) und der lokale Kotlin-Code.
Es wurden keine Funk-, Backend- oder Gerätetests ausgeführt und keine
App-Änderungen vorgenommen. Öffentliche Advisory-Angaben wurden nicht erneut
geprüft. Der frühere Parser-Laborbefund stammt aus den vorhandenen Berichten,
nicht aus diesen Aufnahmen. Der Technical-Writing-Skill hat die Trennung von
Messwerten, Interpretation und Beweisgrenzen angeleitet.

## Umfang und Dateikonsistenz

14 ZIPs und zehn separate JSONL-Dateien enthalten zehn eindeutige Sitzungen.
Je Sitzung wurde der längste Ereignisstand einmal gezählt: **41.920 Ereignisse,
2.198 Advertising-Berichte, 21 Adressen**. Adressen sind keine unabhängig
bestätigten Fahrzeugidentitäten.

Alle ZIP-CRC-Prüfungen bestehen. Alle vorhandenen Ereignislog-Hashes passen zu
den jeweiligen Bytes. Die Sequenzen der zehn längsten Logs sind lückenlos.
Alle 2.198 Advertising-SHA-256-Werte stimmen mit den Rohbytes überein.
Das belegt Konsistenz, nicht Herkunft oder vollständige Funkerfassung.

Die Exporte `105736-187a (1).zip` und `(2).zip` enthalten denselben vollständigen
Log mit 30.261 Ereignissen wie die separate JSONL. Der kleinere Export ohne
Klammer ist ein Live-Zwischenstand mit 17.125 Ereignissen und
`duringCapture:true`. Seine Metadaten nennen noch 16.864 Ereignisse.
Das ist ein veralteter Metadatenstand, kein belegter Verlust im späteren Log.
Auch mehrfach exportierte `104624-2a3f` und `105612-8008` sind keine neuen Läufe.

Zeiten sind Berliner Ortszeit, am 27. Oktober UTC+1. Die Kennung enthält die
lokale Startzeit. Die Dauern beziehen sich auf erstes und letztes Ereignis.

| Sitzung ohne Datum | Dauer ungefähr | Ereignisse | Ads | Inhalt |
| --- | ---: | ---: | ---: | --- |
| `104325-72e9` | 2:50 min | 1.367 | 39 | Ein P18-Gerät, erfolgreiche GATT-Lesung |
| `104616-6514` | 6 s | 30 | 0 | Kein Kandidat |
| `104624-2a3f` | 8:31 min | 8.628 | 876 | Sieben Adressen, vier erfolgreiche GATT-Inventare |
| `105457-3eed` | 1:01 min | 250 | 0 | Baseline-Marker; DOS-Auswahl ohne Ziele oder Ergebnisse |
| `105544-2f84` | 9 s | 3 | 0 | Version 1.0, ohne neue Beobachterinstrumentierung |
| `105559-a49f` | 11 s | 53 | 0 | Ungefiltert 791 Berichte empfangen, kein gespeicherter Buskandidat |
| `105612-8008` | 1:16 min | 1.259 | 76 | READ-Bench vor Abschluss beendet |
| `105736-187a` | 12:56 min | 30.261 | 1.207 | Mehrere Bench-Starts, GATT, Kopplungs- und Schreibversuche |
| `111238-5a2b` | 3 s | 15 | 0 | Kein Buskandidat |
| `111420-1a9c` | 13 s | 54 | 0 | Kein Buskandidat |

`105544-2f84` überlappt mit der neueren App-Aufnahme. Das passt zu einem
getrennten Recorder, belegt aber allein keine zweite Hardware. Sie darf nicht
als instrumentierter Buscheck-Messlauf gelten.

## Bestätigter Fingerprint und Routenzugriff

42 `gatt_read`-Ereignisse stammen aus sieben erfolgreichen Inspektionen an sechs
Adressen. Die Namen lauten jeweils `BlueZ 5.78`, die PnP-Bytes jeweils
`026b1d46024e05`. Das entspricht dem bereits dokumentierten Fingerprint.
Bench-Ergebnisse enthalten zusätzlich gelesene Werte.

| Adresse | Sitzung | PnP-Read-Ereignis |
| --- | --- | ---: |
| `78:C4:0E:C0:2F:CB` | `104325-72e9` | 49 |
| `78:C4:0E:A0:40:B9` | `104624-2a3f` | 1.247 |
| `78:C4:0E:A0:44:F5` | `104624-2a3f` | 1.890 |
| `78:C4:0E:A0:43:BB` | `104624-2a3f` | 2.539 |
| `78:C4:0E:C0:2A:79` | `104624-2a3f` | 7.701 |
| `78:C4:0E:A0:46:81` | `105736-187a` | 68 und 16.958 |

Bei `A0:46:81` bleibt das Ziel `Lemgoer Straße`, während die nächste Haltestelle
von `Westerntor` über `Rathausplatz` zu `Am Bogen` wechselt. Belegstellen in
`105736-187a`: Ereignisse 74, 16.980 und 23.226. Das bestätigt dynamische
Routendaten, nicht einen Firmwaredump.

Ereignis 23.128 inventarisiert fünf Services einschließlich `0x201f/0x2020`
und `0x1f1f/0x1f20`. Die beiden `finding`-Ereignisse 23.129 und 23.227 sind
`severity:info`: Serviceinventar und Routentext, keine zwei Schwachstellen.

Ein früheres `route_read:skipped` mit "fehlt: route" folgt dagegen auf eine
gescheiterte GATT-Inventarisierung. Nicht entdeckt bedeutet hier nicht nicht
vorhanden. Ebenso wenig belegen die erfolglosen Audio-, DFU- und BusCore-Proben
zuverlässig deren Abwesenheit auf dem Ziel.

## Decodergrenze: 833 P18-Berichte ohne Linientext

833 von 2.198 Berichten, rund **37,9 %**, werden als `unknown_protocol`
gespeichert, obwohl der Decoder selbst `protocol:18` erkennt:

- `78:C4:0E:C0:2D:F5`: 546 Berichte.
- `78:C4:0E:C0:2F:73`: 270 Berichte.
- `78:C4:0E:C0:2F:47`: 17 Berichte.

Die Beispiele tragen die erwartete Kennung und die Markierung `0x80`, danach
aber Nullbytes statt Linientext. Der Fehlertext "Protokoll 18 ohne Linientext
an Byte 10" fasst verschiedene Prüfbedingungen zusammen. Hier fehlt nicht
zwingend die Markierung, sondern der Text. Regulärer Betriebszustand, fehlende
IBIS-Daten und andere Varianten lassen sich damit noch nicht unterscheiden.

`CaptureModel.kt:decodeProtocol18` setzt `decoded.ok == false`.
Der Presence-Tracker in `ExploitHub` und die Zielauswahl in
`BenchEngine.onAdvertisement` übernehmen nur erfolgreich dekodierte Geräte.
Die Rohdaten bleiben erhalten, diese drei Adressen fallen aber aus der
Verfügbarkeitsmessung und Bench-Zielauswahl heraus. Das ist eine relevante
Messgrenze meiner App, kein belegter Firmwarefehler.

## Funklücken und falsche Ursachenzuordnung

Der unabhängige Beobachter schreibt **224 Lückenanfänge und 204 Wiederkehren**.
Einige Lücken bleiben bei Aufnahmeende offen. Das sind keine 224 Abstürze.
Die Bench meldet zusätzlich zehn Verdachtsereignisse, drei Wiederkehren und
sechs offene Lücken; ein Verdacht endet ohne Abschluss. Beide Messwege
überlappen. Ihre Zähler dürfen nicht addiert werden.

Klares Beispiel: In `105736-187a` startet um **10:59:10** die rein passive Probe
an `A0:44:EB` (Ereignis 1.966). Schon um **10:59:12** meldet die Bench
56.325 ms Stille (Ereignis 2.017). Das Gerät fehlte also lange vor der Probe.
Das Ergebnis 2.623 erhält trotzdem `status:gap`.

Die längste Zeit zwischen zwei Berichten dieses Geräts beträgt 137,819 Sekunden.
Empfangswerte reichen bis etwa −94 dBm; andere Geräte werden zwischenzeitlich
weiter empfangen. Bewegung, Reichweite, Abschattung, GATT-Verbindungen und
konkurrierende Nutzung sind plausible, nicht bewiesene Erklärungen.
Ein Zielprozess- oder Neustartbeleg fehlt.

`measurement_summary` ist ebenfalls kein vollständiger Ausfallbericht:
Ereignis 1.535 zählt 243 Samples, davon 70 fehlend, nennt aber nur
`downtime_ms:504`. Der Code speichert die erste Lücke und erste Wiederkehr,
nicht die Summe aller Lücken. Schon das erste Sample ist fehlend. Die 504 ms
sind weder Gesamtausfall noch belastbare Crash-Recovery-Zeit.

## Aktive Versuche und fehlender Triggernachweis

In `105736-187a` startet um **11:08:12** eine Kopplungsprobe
(Ereignis 23.408), die nach etwa 40 Sekunden in einen Timeout läuft.
Um **11:09:34** beginnt `action_known` (Ereignis 27.497).
Alle vier Werte erhalten `writeCharacteristic abgelehnt`; Ergebnis 28.793
nennt `0/4 akzeptiert`.

Der letzte Scanbericht für `A0:46:81` liegt schon um **11:08:46.832**
(Ereignis 25.156), also vor den Action-Versuchen. Die spätere Lücke belegt
deshalb keinen durch diese vier Werte ausgelösten Absturz. Eine abgelehnte
Android-Schreiboperation bestätigt auch keine Funkzustellung oder erfolgreiche
Prüfung der serverseitigen Zugriffsrechte.

Es gibt keine Aktions-`http_request`-Ereignisse. Drei erfolgreiche
Netzwerkoperationen laden die Lookup-Datenbank, nicht Fahrgastaktionen.
Die Aufnahmen sind wegen GATT, SDP, Kopplung und Schreibversuchen dennoch
nicht insgesamt passiv.

Es gibt keinen `probe_start` für die drei EIR-Namensproben und keinen
`payload_observation`-Eintrag. Alle gespeicherten Scan Records sind 29, 31 oder
41 Bytes lang. Keiner ist der exakte 259-Byte-Trigger. `risk:DOS` nennt die
ausgewählte Liste, nicht ausgeführte Proben. Eine externe Aussendung lässt
sich aus fehlenden Telefonberichten aber nicht ausschließen. Sender-HCI-Trace,
Zielprotokoll und beigefügte Beweisdateien fehlen vollständig.

## Probleme in meiner Bench

1. **Zusammenfassung verliert Verlauf.** `105736-187a` enthält 28
   `probe_result` und zwei informative `finding`-Ereignisse. Das abschließende
   `bench.json` enthält null Ergebnisse und null Ziele. `start()` ersetzt den
   Zustand, und der Export speichert nur den letzten Lauf. Maßgeblich bleibt
   deshalb der vollständige Ereignislog.
2. **Abbruch ist unvollständig protokolliert.** Sechs Bench-Starts stehen drei
   `bench_stop` und einer `measurement_summary` gegenüber. `stop()` bricht ab,
   ohne selbst einen Stop-Eintrag zu schreiben. Offene Proben bleiben zurück.
3. **"Passiv" ist nicht verbindungsfrei.** `runTarget()` führt vor der Auswahl
   `gatt.discover()` aus, auch bei Auswahl nur `passive`. Diese Option ist keine
   garantiert verbindungsfreie Kontrolle.
4. **Fingerprint-Fehlschläge heißen teilweise `ok`.** "Name unbekannt" steht
   neben erfolgreichen Name-/PnP-Reads desselben Profils. Das zeigt einen
   unvollständigen Versuch, keinen Versionswechsel.
5. **Timeouttexte sind ungenau.** SDP nennt 30 s bei etwa 15.014 ms gemessener
   Dauer, AVRCP 20 s bei etwa 15.009 ms. Verschachtelte Timeouts werden mit
   dem äußeren Probenlimit beschriftet.
6. **`captureWarnings:false` bewertet keine Kausalität.** Die lange Sitzung
   erfüllt Recorderprüfungen, besitzt aber keine belastbare Test-Baseline oder
   Crashbelege. Der einzige manuelle Marker steht in einer Sitzung ohne
   Busdaten. Start-/Stop-Marker und angehängte Beweise fehlen überall.

Der instrumentierte Beobachter läuft ohne protokollierte Scanfehler oder
Queueverluste. 6.197 Health-Samples haben einen Medianabstand von 261 ms,
maximal 326 ms. Das stützt regelmäßige App-Abtastung, nicht lückenlosen Empfang.
Die lange Aufnahme läuft knapp 13 Minuten bis zum Benutzer-Stop ohne sichtbaren
Recorder-Neustart. Das ersetzt keinen Ziel-Watchdog-Test.

## Einordnung gegenüber dem Research

Der Datensatz stärkt E1: Identifikation und normale BLE/GATT-Erreichbarkeit.
Er liefert nicht Herstellerbuild, Backports, Kernel, den betroffenen
Discovery-Empfangspfad oder einen Ziel-Backtrace. Produktbezogene E2 bis E5-Aussagen
bleiben offen. Der ältere Offline-Parserbefund und diese Funkaufnahmen sind
getrennte Belege. Zusammen beweisen sie noch keine Funk-Ausnutzung am Produkt.
Eine Root- oder Codeausführungsbehauptung wird nicht getragen.

Sinnvoll sind zunächst Korrekturen der belegten Auswertungsfehler und eine
stationäre, verbindungsfreie Kontrollaufnahme an einem autorisierten Testgerät.
Für die Produktmeldung fehlen weiterhin Herstellerbuild und Patchzuordnung
sowie korrelierte Sender- und Zielprotokolle. Weitere aktive Versuche im
Fahrbetrieb ersetzen diese Belege nicht.

## SHA-256 der vollständigen Ereignislogs

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
