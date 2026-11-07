# Bewertung der Buscheck-Aufnahmen vom Abend des 27. Oktober

[English](../en/buscheck-evening-evaluation-2026-10-28.md) · [Deutsch](buscheck-evening-evaluation-2026-10-28.md)

## Ergebnis

Die Aufnahmen belegen anhaltenden Zugriff auf Live-Routendaten der Linie 11 ohne
die Original-App. Sie bestätigen den zuvor beobachteten BlueZ-5.78-Fingerprint
und die erwarteten GATT-Services. Sie belegen keinen Zielabsturz, keine
erfolgreiche Fahrzeugaktion, keine Übertragung des exakten Namens, keine
Codeausführung und kein Root.

Der nützlichste neue Befund ist ein Messfehler: Dieselbe Adresse der Linie 11
sendet kurzzeitig Protokoll 18 ohne Linientext. Mein Decoder hört dann auf, die
Präsenz zu aktualisieren, obwohl weiter Rohpakete eintreffen. Mindestens eine
gemeldete Verfügbarkeitslücke ist daher gar kein Funkausfall.

Dies ist eine Offline-Auswertung der fünf gelieferten Anhänge, der
[Übergabe](handover-2026-10-26.md) und des aktuellen lokalen
Logger-Quellcodes. Für diese Auswertung wurden keine Bluetooth-, Backend- oder
Geräteanfragen ausgeführt. Der frühere Parser-ASan-Befund der Übergabe wurde
nicht erneut ausgeführt. Öffentliche Schwachstellenkennungen und
Upstream-Patchbehauptungen wurden nicht unabhängig geprüft. Der
Reverse-Engineering-Skill hat die Unterscheidung zwischen Beobachtungen und
Schlussfolgerungen angeleitet. Der Technical-Writing-Skill hat die
Berichtsstruktur angeleitet. REA-Werkzeuge waren in dieser Sitzung nicht
verbunden, daher stammen die Belege unten aus gewöhnlicher ZIP-, JSON-, Hash-
und Quellcode-Prüfung, nicht aus REA-Evidence-Einträgen.

## Die Anhänge enthalten zwei Sitzungen

Alle Zeiten unten sind Europe/Berlin, UTC+1 am 27. Oktober 2026.
Ereignis-`sequence`-Nummern sind Verweise in die JSONL der genannten Sitzung,
keine Markdown-Zeilennummern.

- `20261027-181517-b9e9 (1).zip` ist die abgeschlossene lange Sitzung:
  18:15:18-18:34:38, 31.485 Ereignisse, 7.918 Advertising-Berichte und
  11 Adressen.
- `20261027-181517-b9e9.zip` ist ein Live-Export der ersten 5.440 Ereignisse
  derselben Sitzung, endend um 18:20:18.924. Diese Ereignisse passen zum
  abgeschlossenen Log. Es ist kein weiteres Experiment. Seine
  Sitzungsmetadaten nennen noch 5.271 Ereignisse, während die zugehörige
  Cutoff-Zusammenfassung korrekt 5.440 nennt. Das ist ein veralteter
  Live-Schnappschuss, kein Beleg dafür, dass das abgeschlossene Log diese
  Ereignisse verloren hat.
- Die lange eigenständige JSONL ist byte-identisch mit der JSONL des
  abgeschlossenen ZIP.
- `20261027-181202-e3bd.zip` und seine eigenständige JSONL enthalten dieselbe
  kurze Sitzung: 18:12:03-18:12:26, 216 Ereignisse und 116
  Advertising-Berichte von einer Adresse.

Nach Deduplizierung gibt es 31.701 Ereignisse und 8.034 Advertising-Berichte von
12 Adressen. Adressen sind keine unabhängig bestätigten physischen
Busidentitäten. Nur die lange Sitzung identifiziert Linie 11. Die kurze Sitzung
hat keine dekodierte Linie.

Alle drei ZIP-CRC-Prüfungen bestehen. Beide Hashes abgeschlossener JSONL passen
zu ihren Metadaten und eigenständigen Gegenstücken. Ereignissequenzen sind
durchgehend. Alle exportierten Advertising-Hashes passen zu ihren Rohbytes.
Diese Prüfungen belegen interne Konsistenz, nicht Authentizität oder
vollständigen Funkempfang.

## Zugriff auf Linie-11-Daten ist gut belegt

Die Hauptadresse ist `78:C4:0E:C0:2B:D7`, Profil `p-8eef9540`. Sie erscheint von
18:16:41.816 bis 18:33:29.144 in 7.473 Scanberichten. Davon dekodieren 7.410 als
Linie 11 und 63 ohne Linientext. RSSI reicht von −94 bis −46 dBm, Median
−57 dBm.

Die lange Sitzung enthält 31 erfolgreiche automatische GATT-Inventare über fünf
Adressen und 186 erfolgreiche `gatt_read`-Callbacks. Linie 11 trägt 26 Inventare
und 156 dieser Reads bei. Bench-Ergebnisse enthalten zusätzliche Reads außerhalb
dieser Callback-Zählung.

Linie 11 liefert wiederholt den Namen `BlueZ 5.78` und die PnP-Bytes
`026b1d46024e05`. Das Serviceinventar umfasst GAP, GATT, Device Information, den
Routendienst `0x201f` mit lesbarem `0x2020` und den Aktionsdienst `0x1f1f` mit
beschreibbarem `0x1f20`. Die Bench-Inventare melden fünf Services und sechs
lesbare Werte. Die drei Fingerprint- und Inventarergebnisse wiederholen denselben
Grundaufbau.

Routenbytes enthalten Ziel- und Nächster-Halt-Zeichenketten, getrennt durch
`0x1d`. Das Ziel ist normalerweise `Heinz NixdorfWendeschleife`. Beobachtungen
des nächsten Halts umfassen die folgende Folge:

- 18:16:45, Ereignis 414: `Langer Weg`.
- 18:17:31, Bench-Ereignis 1.402: `Fröbelstraße`.
- 18:19:55, Ereignis 4.872: `Gierstor`.
- 18:20:07, Ereignis 5.168: `Detmolder Tor`.
- 18:22:04, Ereignis 7.590: `Maspernplatz`.
- 18:23:49, Ereignis 9.850: `Neuhäuser Tor`.
- 18:25:58, Ereignis 12.764: `Westerntor`.
- 18:31:47, Ereignis 24.273: `Hauptbahnhof`.

Das belegt sich ändernde Betriebsdaten, nicht nur einen statischen Gerätenamen.
Reads gelingen vor dem protokollierten Kopplungsversuch. Dieser Versuch bestätigt
nie eine neue Bindung. Die Aufnahme belegt nicht unabhängig die frühere
Bindungsgeschichte des Telefons oder die vollständige Sicherheitsrichtlinie des
Ziels.

Der Fingerprint ist kein Firmwaredump. Er identifiziert keine Herstellerpatches,
beweist keinen ungepatchten Parser und belegt nicht, dass der Bus eingehende
erweiterte Advertisements scannt. Bluetooth-Advertising und GATT-Bereitstellung
belegen für sich nicht, dass der betroffene Empfangspfad aktiv ist.

## Die aktive Bench belegte keine erfolgreichen Aktionen

Die lange Sitzung enthält drei abgeschlossene Bench-Läufe: einen DOS-ausgewählten
Lauf mit 25 Ergebnissen und zwei READ-ausgewählte Läufe mit je 13 Ergebnissen.
Es gibt 51 Probenergebnisse und neun informative Findings. Diese Findings sind
drei wiederholte Fingerprints, drei Inventare und drei Routenreads, nicht neun
Schwachstellen. `bench.json` bewahrt nur den letzten Lauf mit 13 Ergebnissen.

Wichtige Ergebnisse im ersten Lauf sind:

- Ereignis 2.549: Kopplung läuft nach etwa 40 Sekunden in einen Timeout.
- Ereignis 2.725: bekannte Aktionsschreibvorgänge melden `0/4` akzeptiert.
- Ereignis 2.974: die Aktionsmatrix meldet `0/24` akzeptiert.
- Ereignis 3.708: der Aktionsdurchlauf meldet `0/30` akzeptiert.
- Ereignis 3.033: alle drei Backend-Anfragen melden HTTP 200 mit
  `accepted=false`. Nur der reduzierte Status wird behalten, keine
  Antwortkörper, die den Grund erklären. Keine erfolgreiche Backend-Aktion ist
  belegt. Das Fehlen separater `http_request`-Ereignisse bedeutet nicht, dass
  keine Anfragen erfolgten: dieser Bench-Pfad ruft `BusRequests.send` direkt auf.
- Ereignis 3.105: alle vier MTU-Anfragen liefern 517. Das ist erfolgreiche
  MTU-API-Aushandlung, kein Beleg für vier verschiedene tatsächlich genutzte
  Funk-MTUs oder einen Fehler.
- Ereignis 3.385: der Reliable-Write-Test meldet Fehlschlag.
- Ereignisse 3.471, 3.502 und 3.544: alle drei EIR-Namensproben melden
  ausdrücklich `unsupported`, mit `exactPayloadSent:false`.

`writeCharacteristic abgelehnt` wird von der App ausgelöst, wenn Android die
Übergabe ablehnt, vor einem erfolgreichen entfernten Write-Callback. Diese
Fehlschläge beweisen nicht, dass der Server die Bytes empfangen und abgelehnt hat
oder dass seine Zugriffskontrolle einen Angriff abwehrte. Siehe
`BenchEngine.kt:553`.

Das Abonnement von Service Changed meldet Erfolg, aber es wird keine
Service-Changed-Indication protokolliert. SDP und AVRCP laufen in Timeouts.
RFCOMM-, BAP-, BASS-, BusCore- und DFU-Ergebnisse belegen keine universelle
Abwesenheit dieser Funktionen. Ihr Umfang sind die konkreten Discovery- und
Verbindungsversuche in dieser Aufnahme.

## Kein Experiment zum exakten Namen oder Absturz ist belegt

Alle 8.034 gespeicherten Scan Records sind 29, 31 oder 41 Bytes lang und alle von
Android als Legacy und vollständig markiert. Es ist kein `payload_observation`
vorhanden. Keines der ZIPs enthält Sender-Traces, Ziel-Daemon-Logs oder
Absturzartefakte. Die lange Sitzung hat nur einen manuellen `test_stop`-Marker um
18:26:35.507, Ereignis 13.466, ausdrücklich mit `transmissionConfirmed:false`
markiert. Es gibt keinen Basis- oder Teststart-Marker.

Die EIR-Proben des Telefons haben den erforderlichen Namen ausdrücklich nicht
gesendet. Diese Dateien können nicht belegen, ob ein externes Pi oder S3 ihn
gesendet hat. Kein aufgezeichneter Treffer ist kein Beweis für keine
Übertragung: dies war ein gefilterter Android-Scan, keine unabhängige
Roh-Empfängeraufnahme.

Die lange Sitzung protokolliert 135 Startpunkte von Beleglücken und 125
Wiederkehren über verfolgte Adressen. Linie 11 hat 36 Startpunkte und 35
Wiederkehren. Die letzte offene Lücke und Lücken von vorbeifahrenden Geräten sind
keine Prozessabsturzzahlen.

Das längste wiederhergestellte Linie-11-Intervall zwischen Berichten ist
13.321 ms, endend um 18:33:04.019, Ereignis 27.564. Die um die Aktualität
bereinigte Lücke ist 11.821 ms. Sie tritt deutlich nach dem Ende der letzten
Bench um 18:25:41.243 und nach dem manuellen Stoppmarker auf. Zehn weitere
Advertisements treffen während dieses Intervalls ein, es ist also keine
vollständige Abwesenheit von Berichten des Telefons. Die Ursache bleibt
unbekannt. Der letzte Bericht von Linie 11 hat RSSI −94 dBm, das endgültige
Verschwinden ist also auch mit dem Verlassen der Empfangsreichweite vereinbar.
Keine der beiden Beobachtungen beweist die Ursache.

Die drei Zusammenfassungen der Bench enthalten 597, 235 und 234 Samples, mit 1,
0 und 8 fehlenden Samples. Die beiden Zusammenfassungen mit Lücken zeigen jeweils
252 ms Ausfallzeit. Der Code behält nur das erste fehlende Sample und die erste
Wiederkehr. Diese Zahl ist nicht Gesamtausfallzeit, präzise Funkausfallzeit oder
Daemon-Neustartzeit. Siehe `BenchEngine.kt:306` und `EvidenceCapture.kt:16`.

Der Beobachter selbst erscheint stabil: 4.409 Health-Samples der langen Sitzung
melden alle Betriebsstatus, mit einem Medianintervall von 258,8 ms und maximal
329,0 ms. Es werden keine verworfenen Ereignisse, Scanfehler oder
Capture-Gap-Ereignisse aufgezeichnet. Das stützt die Kontinuität des Recorders,
nicht ununterbrochenen Empfang von jedem Bus.

## Die Aufnahmen zeigen Grenzen meiner App

### Präsenz hängt fälschlich davon ab, eine Linie zu haben

Die 116 Berichte der kurzen Sitzung sind alle Protokoll 18 mit der erwarteten
Markierung, aber ohne Linientext. Die READ-Bench beginnt bei Ereignis 44 und
stoppt bei Ereignis 143 mit null Zielen und null Ergebnissen. Für diese Adresse
werden keine GATT-Reads oder Evidence-Presence-Samples erzeugt, obwohl ihre
Pakete empfangen werden.

Dasselbe Phänomen tritt auf Linie 11 auf, nicht nur bei einem unbekannten Gerät:

- Ereignisse 5.502-5.600 enthalten 41 solche Berichte zwischen 18:20:22.033 und
  18:20:27.084.
- Ereignisse 11.967-12.025 enthalten 22 zwischen 18:25:27.699 und 18:25:30.131.

Bei Ereignis 5.605 behauptet der Tracker ein Intervall von 5.216 ms zwischen
Berichten, obwohl während dieses Intervalls Roh-Advertisements eintrafen. Er
misst die Zeit zwischen geeigneten dekodierten Berichten, nicht notwendigerweise
zwischen Funkberichten. `ExploitHub.kt:429` und `BenchEngine.kt:187` verwerfen
`decoded.ok == false` für Präsenz- und Zielaktualisierungen.
`CaptureModel.kt:167` kennzeichnet fehlenden Linientext als `unknown_protocol`,
auch wenn das Protokollfeld ausdrücklich 18 ist.

Die andere Adresse der langen Sitzung ohne Linie, `78:C4:0E:C0:2F:73`, trägt
weitere 138 verworfene Berichte bei. Es gibt 317 Decoderfehler ohne Linie über
die beiden Sitzungen. Das ist kein Beleg für 317 fehlerhafte Funkpakete oder
Abstürze.

Die rohe Routen-Characteristic hat außerdem manchmal ein leeres Ziel: Ereignisse
5.643, 12.381 und 21.359 behalten eine Nächster-Halt-Zeichenkette, aber ein
leeres erstes Feld. Nicht jedes fehlende Ziel in der UI kann daher allein auf
meinen Lookup oder Decoder geschoben werden. Die Aufnahmen erklären den Grund des
Ziels nicht.

### Bench-Zusammenfassungen können fehlgeschlagene Operationen als erfolgreich bezeichnen

Alle drei `post_inventory`-Ergebnisse, Ereignisse 4.816, 9.804 und 12.335, sagen
`status:ok` und "6 readable values". Alle sechs Werte in jedem Ergebnis sind
tatsächlich `error: readCharacteristic abgelehnt`. `BenchEngine.kt:997` zählt
Wörterbucheinträge, einschließlich Fehlern, statt erfolgreicher Reads.

Ebenso bedeutet `http_actions:ok` in diesem Lauf null Bestätigungen, und
`att_descriptors:ok` enthält einen abgelehnten Descriptor-Read.
Statusbezeichnungen brauchen eine Auswertung pro Operation, nicht einen
einzelnen grünen Erfolgsanzeiger.

Es gibt außerdem eine relevante Schwäche im Verbindungslebenszyklus:
`BenchGatt.discover()` liefert zwischengespeicherte Services, bevor die
Konnektivität geprüft wird. Die Behandlung von Trennungen löscht dieses Inventar
nicht. Spätere Operationen können versuchen, veralteten Zustand zu nutzen. Das
ist ein plausibler Beitrag zu lokalen Read- und Write-Ablehnungen, keine
bewiesene Diagnose dieser konkreten Fehlschläge. Bench-Callbacks fehlen die
Verbindungs- und numerischen Übergabedetails, die zur Klärung der Ursache nötig
wären.

## Was die Belege als Nächstes stützen

Das praktische Ziel des Datenlesens ist gestützt. Ein Produktionsbegleiter kann
das Advertisement für die Linienidentität und einen begrenzten Read von `0x2020`
für aktuelles Ziel und nächsten Halt nutzen. Der Datensatz belegt keine Latenz-,
Zuverlässigkeits- oder Sicherheitsgarantien für jedes Fahrzeug.

Die erste Messpriorität ist, rohe Funkpräsenz, Protokollerkenntnis und
Routenverfügbarkeit zu trennen. Das Replay dieser Logs sollte alle 63
Linie-11-Pakete ohne Linie sichtbar halten, die Adresse der kurzen Sitzung
verfolgen und in jedem fehlgeschlagenen Abschlussinventar null erfolgreiche Werte
zeigen. Die Laufaggregation muss alle 51 Probenergebnisse behalten statt nur der
letzten 13.

Das nächste nützliche Experiment ist eine stationäre passive Baseline auf einem
eigenen oder ausdrücklich autorisierten Testgerät, mit automatischen GATT-Reads
und deaktivierter Bench. Ein separater Read-only-Lauf kann die Wirkung von
Verbindungen messen. Die aktuelle Aufnahme mischt Scannen, wiederholte Reads,
Abonnements, Kopplung, Writes und Backend-Anfragen und ist daher nicht diese
Baseline.

Auf einem eigenen Testperipheriegerät sind Reconnect-Behandlung zu validieren und
numerische Android-Übergabeergebnisse, Verbindungszustand,
Characteristic-Eigenschaften und ATT-Callbacks aufzuzeichnen. Ergänze vor und
nach einem Test einen erfolgreichen frischen Read. Das kann eine defekte
Client-Sitzung von einem nicht verfügbaren oder ablehnenden Server trennen.

Für die Sicherheitsfrage fehlt als Beleg ein kontrollierter autorisierter
Laborvergleich mit identifizierten Zielbuilds, geprüften Sender- und
Empfängeraufnahmen und zielseitigen Daemon- oder Absturzlogs. Schließe eine
unbehandelte Kontrolle und einen Vergleich mit gepatchtem Build bei
abgeglichenen Uhren ein. Der `/crash`-Endpunkt des Pi testet absichtliches
Entfernen von Advertising, nicht die Parser-Schwachstelle. Weitere disruptive
Tests in fahrendem Passagierbetrieb würden diese Beleglücken nicht sicher
schließen. Firmware-Identität und der betroffene Empfangspfad bleiben wichtiger
als weitere Feldprobversuche.

## Hashes abgeschlossener Logs

```text
20261027-181517-b9e9  a986c108ee66a67fffedcc656cd549727ead8ccfefc8950ecef04aba6f84d017
20261027-181202-e3bd  5cf44147887b0c0c521d0f23d48281a938405242f12d79a54c0bdffade4075ba
```
