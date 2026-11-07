# Einen Buscheck-Laborlauf aufzeichnen

[English](../en/buscheck-evidence-capture.md) · [Deutsch](buscheck-evidence-capture.md)

Nutze deinen eigenen virtuellen Pi-Bus oder ein anderes Testgerät, das du testen
darfst. Das Telefon zeichnet Beobachtungen auf. Es belegt aus Advertising-Stille
allein keinen Absturz oder eine Schwachstelle.

## Die Aufzeichnung vorbereiten

1. Installiere `exploit/build/outputs/apk/debug/exploit-debug.apk`. Dieser Build
   ist `1.1-buscheck-evidence`, Versionscode 2.
2. Öffne Buscheck. Lass die aktive Bench gestoppt.
3. Für eine passive Baseline schalte **Busse automatisch auslesen** aus, bevor
   du die Aufnahme startest. Bestehende GATT-Inspektion kann Namen, PnP-IDs,
   Services und lesbare Characteristics auf einem autorisierten Testgerät
   sammeln, aber eine Verbindung kann sein Advertising-Verhalten ändern.
   Zeichne Reads getrennt auf.
4. Starte **Aufnahme starten** und erteile die angeforderten Berechtigungen. Die
   Vordergrundbenachrichtigung hält die Aufnahme sichtbar. Lass das Telefon in
   der Nähe des Testgeräts.
5. Ergänze eine Notiz, die Adresse, Build, Testfall, Sender und Bedingungen des
   Testgeräts benennt. Verlass dich nicht allein auf ein Adresspräfix oder eine
   Version, um einen verwundbaren Build zu identifizieren.
6. Bestätige, dass die rohen Advertisements des Busses erscheinen. Drücke
   **Basis markieren** und zeichne mindestens 30 Sekunden Normalverhalten auf.

## Test und Wiederherstellung aufzeichnen

1. Drücke **Start markieren** unmittelbar vor deinem autorisierten Labortest.
   Das zeichnet einen manuellen Marker auf, keine bestätigte Übertragung.
2. Zeichne durch Ereignis und Wiederherstellung weiter auf. Bleib an derselben
   Position. Eine Lücke im `/crash`-Test des virtuellen Pi-Busses validiert nur
   die Beobachtungs- und Wiederherstellungsaufzeichnung. Dieser Endpunkt entfernt
   absichtlich Advertising und ist kein Daemon-Absturz-Reproduzierer.
3. Drücke **Stopp markieren**, wenn der externe Test endet, und zeichne dann
   weitere 30 Sekunden auf. Die Hauptschaltfläche **Stopp** der Aufnahme beendet
   die Aufzeichnung; der Marker stoppt die Aufnahme nicht und steuert keinen
   Sender.
4. Nutze **Datei beifügen**, solange die Aufnahme noch läuft, um die originale
   Sender-HCI-Aufnahme, Ziel-Daemon-Logs, Crash-Backtrace und Laborergebnisse
   anzuhängen. Jeder Anhang ist auf 16 MiB begrenzt, mit höchstens 16 pro
   Sitzung. Die Anhangsverarbeitung kann die Abtastung verzögern. Hänge nach der
   Messung an und halte die Originaldateien auch außerhalb der App.
5. Stoppe die Aufnahme. Wähle **Export**, dann **Ganze Sitzung teilen (ZIP)** oder
   **ZIP in Downloads/Brunel speichern**. Bevorzuge ZIP gegenüber der
   eigenständigen JSONL, wenn du Zusammenfassung und Anhänge brauchst.

## Die exportierten Belege prüfen

1. Lass das ZIP unverändert. Prüfe `eventsSha256` aus `evidence-summary.json`
   gegen die exakten `events.jsonl`-Bytes. Das prüft Konsistenz, nicht wer die
   Aufnahme erzeugt hat. Ein Live-Export hat einen Cutoff und ist kein
   abgeschlossener Lauf.
2. Prüfe `captureWarnings`, `sequenceErrors`, `observer_health`, `capture_gap`
   und `scan_error`. Die Zusammenfassung behauptet nicht, dass ein warnungsfreier
   Scan beweist, dass das Funkgerät durchgehend funktionierte.
3. Prüfe `payload_observation`. Nur `exact_259` identifiziert die vollständigen
   erforderlichen 259 Bytes in einem Android-Scan Record.
   `name_match_other_layout`, `service_data_not_name` und `incomplete_report`
   sind keine gleichwertigen Treffer. Kein Treffer beweist nicht, dass keine
   Übertragung erfolgte.
4. Prüfe `evidence_presence`, `evidence_gap_start`, `evidence_gap_end` und
   `evidence_gap_invalidated`. Die Abtastung läuft nominal alle 250 ms. Ein Bus
   gilt 1.500 ms nach seinem letzten Bericht als aktuell. Das sind Berichtslücken,
   keine exakten Ausfallzeiten. Die Wiederherstellung umfasst sowohl die
   Lückenschätzung als auch das Intervall zwischen Berichten. Unbekannte Samples
   haben `visible: null`.
5. Vergleiche die Rohbytes des Telefons, RSSI, PHY, SID, Datenvollständigkeitsstatus,
   Scan-Zeitstempel und Empfangszeitstempel mit dem Sender-Trace. Die
   Ereignissequenz ist die Schreibreihenfolge. UTC- und verstrichene Zeitstempel
   bewahren den Auftretenszeitpunkt, der bei in der Warteschlange stehenden
   Ereignissen von der Schreibreihenfolge abweichen kann. Monotone Uhren
   verschiedener Geräte lassen sich nicht direkt vergleichen.
6. Prüfe die Anhang-Hashes. Dateien unter `evidence/` behalten ihre Originalbytes
   mit generierten Namen. `evidence_attachment` zeichnet den Originalnamen, die
   Größe und SHA-256 auf. Dateiinhalte werden vom Bediener geliefert und nicht
   automatisch als Absturzbeweis validiert.
7. Um einen Schwachstellenbefund zu stützen, korreliere die gesendeten Bytes mit
   einem zielseitigen Absturz und Backtrace auf dem identifizierten Build.
   Schließe denselben autorisierten Labortest gegen einen gepatchten Build und
   einen Kontrolllauf ohne den Trigger ein. Dokumentiere den Uhrabgleich und jede
   Zeitunsicherheit.

Die Zusammenfassung kennzeichnet Telefonbeobachtungen immer als
`observations_only_not_proof_of_exploitation`. Demoaufnahmen sind ausdrücklich
`demo_not_evidence`. Die Namensproben von Android liefern `unsupported`; die App
meldet ihren Service-Data-Ersatz nicht als Reproduktion des exakten Namens.

Der Recorder speichert Rohdaten für Buskandidaten und relevante Payloads. Andere
empfangene Geräte tragen aggregierte Health-Zähler bei, keine
Rohgerätedatensätze. Der Standardfilter enthält Service-UUID `0x1f1f`, Hersteller
`0x7d78` und Service-Data `0x1f1f`. Ein Payload nur mit Namen ohne diese Felder
erfordert die ungefilterte Scan-Option. Die Zielverfolgung ist auf 128 Adressen
pro Sitzung begrenzt; ein `evidence_limit`-Ereignis warnt, wenn diese Grenze
erreicht wird. Die Zusammenfassung enthält bis zu 1.000 Marker und 1.000
Lückenereignisse. Die JSONL behält die vollständige Zeitachse.
