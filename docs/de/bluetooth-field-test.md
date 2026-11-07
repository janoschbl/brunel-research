# Busbeobachtungen in Paderborn aufzeichnen

[English](../en/bluetooth-field-test.md) · [Deutsch](bluetooth-field-test.md)

Geplantes Datum: 24. Oktober 2026. Diese Checkliste gilt, nachdem die [Capture-Seiten-Spezifikation](bluetooth-capture-spec.md) umgesetzt ist. Die aktuelle App bietet den spezifizierten Recorder noch nicht.

## Das Telefon vor der Abfahrt vorbereiten

1. Installiere den Debug-Build auf dem physischen Telefon, das du mitnimmst.
2. Erteile die Berechtigungen, die die Capture-Seite anfordert.
3. Starte eine kurze Testsitzung.
4. Prüfe, dass die Seite eine wachsende Dauer und einen gesunden Writer-Zustand zeigt.
5. Füge eine Notiz mit einem erkennbaren Testlabel hinzu.
6. Stoppe die Sitzung.
7. Exportiere das einfache JSONL-Log und das vollständige Sitzungs-ZIP.
8. Öffne den Export auf einem anderen Gerät.
9. Prüfe, dass die Notiz, die Sitzungsmetadaten und das Stop-Ereignis vorhanden sind.
10. Lade die Namensnachschlage-Datenbank, bevor du die Netzabdeckung verlässt.
11. Prüfe den verfügbaren Speicher und den Akkustand.
12. Packe eine Powerbank ein.

Wenn ein zweites Testgerät verfügbar ist, sende markierte Simulator-Advertisements. Prüfe, dass ihre Rohbytes in einer Testsitzung erscheinen. Zähle Simulator-Ergebnisse nicht als Beleg für echte Busse.

## Unterbrechungen vor dem Besuch prüfen

1. Starte eine weitere Test-Capture.
2. Öffne einen anderen App-Bildschirm.
3. Kehre zur Debug-Seite zurück und prüfe die Kontinuität.
4. Sperre das Telefon für zwei Minuten.
5. Entsperre das Telefon und prüfe auf eine Capture-Lücke.
6. Deaktiviere Bluetooth.
7. Prüfe, dass das Log die Unterbrechung aufzeichnet.
8. Aktiviere Bluetooth und prüfe das aufgezeichnete Fortsetzungsverhalten.
9. Stoppe und exportiere die Sitzung.

Wenn Capture bei gesperrtem Bildschirm nicht verifiziert ist, halte die App während der Beobachtungen sichtbar. Nimm nicht an, dass eine aktive Benachrichtigung den weiteren Paketempfang beweist.

## Die Feldsitzung aufzeichnen

1. Starte die Capture, bevor der erste Bus ankommt.
2. Lass den standardmäßigen passiven Modus aktiviert.
3. Füge eine Notiz mit dem Haltestellennamen und deinem Beobachtungspunkt hinzu.
4. Wenn ein Bus ankommt, notiere seine sichtbare Linie und sein Ziel.
5. Wenn sichtbar, notiere die Wagennummer getrennt von der dekodierten Hardware-ID.
6. Prüfe die Zähler für empfangene und persistierte Ereignisse.
7. Behalte unaufgelöste Bus-Einträge und Parse-Fehler.
8. Beobachte nach Möglichkeit mehrere Busse auf derselben Linie.
9. Füge Notizen hinzu, wenn du einsteigst, aussteigst oder zu einer anderen Haltestelle wechselst.
10. Exportiere einen Checkpoint nach der ersten brauchbaren Capture.

Halte externe Beobachtungen getrennt von dekodierten Feldern. Ein Paket mit einer Nächste-Haltestelle-ID beweist für sich genommen nicht, dass der Bus an dieser Haltestelle ist.

## Ein autorisiertes Fahrzeug inspizieren

1. Bestätige, dass das Fahrzeug im autorisierten Testumfang liegt.
2. Wähle das beobachtete Gerät in der Debug-Seite aus.
3. Starte eine reine Leseinspektion.
4. Warte auf den Abschluss oder den aufgezeichneten Timeout.
5. Prüfe die entdeckten UUIDs und jedes Leseergebnis auf der Allowlist.
6. Prüfe, dass die Verbindung geschlossen wurde.

Wenn Authentifizierung oder Pairing nötig ist, behalte das blockierte Ergebnis. Fahre nicht in die Authentifizierung fort und sende keine Fahrzeugsteuerbefehle.

## Die Aufzeichnung sichern

1. Stoppe die Capture am Ende der Sitzung.
2. Warte, bis der Writer seinen letzten Flush abgeschlossen hat.
3. Exportiere das vollständige Sitzungs-ZIP.
4. Kopiere das ZIP auf ein zweites Gerät.
5. Öffne `events.jsonl` und prüfe den endgültigen Sitzungszustand.
6. Prüfe jede gemeldete Drop-Zahl, Lücke oder Warnung zu unvollständiger Capture.
7. Behalte die Originalaufzeichnung, bis der kopierte Export verifiziert ist.

Bevor du einen Export teilst, prüfe Bluetooth-Adressen, Standortdaten und Freitextnotizen. Verwende für öffentliche Berichte eine redigierte Kopie.

## Die Beobachtungen danach auswerten

1. Vergleiche die Notizen zu sichtbarer Linie und Ziel mit den dekodierten Feldern.
2. Prüfe, ob Firmen-ID `4` und Protokoll `16` auf echten Bussen erscheinen.
3. Prüfe, ob jede beobachtete Adresse eine konsistente Hardware-ID hat.
4. Prüfe auf mehrere Adressen mit derselben Hardware-ID.
5. Vergleiche Änderungen von Linie, Kurs, Ziel und nächster Haltestelle über die Zeit.
6. Liste unbekannte Payloads und Parserfehler auf, bevor du den Dekoder änderst.
7. Vergleiche reine Scan-Sitzungen mit autorisierten Inspektionssitzungen auf Unterbrechungen.
8. Liste Verbindungsfehler nach ursprünglichem Statuscode und verstrichener Zeit auf.

Behandle erfolgreiche Entdeckung, erfolgreiche Reads und die Zustellung von Fahrgaststeuerung als getrennte Ergebnisse. Dieser Capture-Plan testet die Zustellung von Fahrgaststeuerung nicht.
