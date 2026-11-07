# Field Runbook

[English](../en/field-runbook.md) · [Deutsch](field-runbook.md)

Für einen Buscheck-Lauf in einem Bus. Lies zuerst `docs/de/handover-2026-10-26.md`.

## Vor dem Einsteigen

1. Lade Telefon und Pi. Packe eine Powerbank ein.
2. Installiere `exploit/build/outputs/apk/debug/exploit-debug.apk`
   (SHA-256: `a49f0f1b5c060969ced0b9c0610944cff78c73b917ba7458b6a3c3158e6f9027`).
3. Erteile Berechtigungen für Geräte in der Nähe, Standort und Benachrichtigungen.
4. Starte eine Capture und prüfe, dass Advertisements ankommen.
5. Starte den Pi-Advertiser und öffne `http://ubuntu.local:8080/`.
6. Entscheide die Stufe. `Nur lesen` ist sicher. `Aktionen` schreibt echte Anfragen.
   `Nur EIR` kann `bluetoothd` neu starten.

## Im Bus

1. Starte die Capture, bevor der Bus ankommt. Drücke **Start** auf der Pi-Seite.
2. Notiere die Haltestelle, die sichtbare Linie und die Wagennummer.
3. Warte auf ein dekodiertes Busprofil. Wähle keinen Simulator.
4. Beginne mit `read` oder dem Preset `Nur lesen`. Prüfe den Routentext gegen das
   sichtbare Ziel.
5. Wenn die Route passt, führe nur das Preset `Aktionen` oder `action_known` aus.
6. Führe `Nur EIR` oder `Alles` nur in einem Bus aus, den du beobachten kannst. Die App zeichnet die
   Präsenz alle 250 ms auf und zeigt die Lücke und die Erholung.
7. Stoppe Buscheck und den Pi-Advertiser, bevor du den Bus verlässt.
8. Exportiere die Sitzung als ZIP und kopiere sie vom Telefon herunter.

## Was zu erfassen ist

- sichtbare Linie, Ziel, Wagennummer
- Adresse, RSSI, Name, Protokoll
- welche Probes liefen, welche übersprungen wurden
- Absturzzeit, Erholungszeit, ob das Modul zurückkam
- ob sich das Fahrgastdisplay oder die Ansage geändert hat

## Nach dem Lauf

1. Behalte das Original-ZIP. Bearbeite es nicht.
2. Führe `brunel report` auf der Sitzung aus.
3. Vergleiche den Absturz mit dem Laborergebnis. Ein Absturz ohne Labortreffer ist ein
   Kandidat, kein Befund.
4. Wiederhole das auf einem zweiten Bus mit demselben Build, bevor du berichtest.
5. Prüfe die Backend-Antworten getrennt vom Funkergebnis.

## Abbruch

Stoppe Bench und Capture, wenn:

- das Modul nach zwei Minuten nicht zurückkommt
- der Bus die Haltestelle verlässt
- das Telefon überhitzt oder der Akku schnell fällt
- eine Fahrgastaktion eindeutig unerwünscht ist
