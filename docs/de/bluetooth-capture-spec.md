# Spezifikation der Bluetooth-Aufnahmeseite

[English](../en/bluetooth-capture-spec.md) · [Deutsch](bluetooth-capture-spec.md)

Status: vorgeschlagene Funktion. Dieses Dokument bedeutet nicht, dass Aufnahme,
persistente Profile oder GATT-Inspektion umgesetzt sind.

## Zweck

Die Debug-Seite zeichnet Bus-Advertisements und Read-only-Inspektionsergebnisse
während einer Feldsitzung auf. Ihre Ausgabe unterstützt die spätere Auswertung
ohne einen weiteren Besuch am Fahrzeug.

Das erste Ziel ist der Besuch in Paderborn am 24. Oktober 2026. Die
[Protokollerklärung](bluetooth-radar.md) liefert Kontext. Die
[Feldtest-Checkliste](bluetooth-field-test.md) definiert die geplanten
Prüfungen.

## Bestehende Umsetzung

Brunel ist eine native Kotlin-App mit Jetpack Compose. Relevante bestehende
Dateien sind:

- `app/src/main/java/dev/padermodern/companion/PassiveBusScanner.kt`: gefilterter
  Scan im Balanced-Modus nach BusAccess-Advertisements. Adressen bleiben im
  Speicher. Unbekannte Pakete und Simulator-Datensätze werden verworfen.
- `app/src/main/java/dev/padermodern/data/BusAdvertisement.kt`: strikter Parser
  für Protokoll 16 und Firma 4. Er liefert aufgelöste numerische Felder, keine
  vollständige Rohaufnahme.
- `app/src/main/java/dev/padermodern/companion/BusNameRepository.kt`:
  Namenssuche aus einer heruntergeladenen SQLite-Datenbank im App-Cache.
- `app/src/main/java/dev/padermodern/companion/TripCompanionService.kt`:
  bestehender Reisebegleitdienst, kein geprüfter Debug-Recorder.

Die Debug-Funktion braucht einen Rohbeobachtungspfad vor `BusAdvertisement.parse`.
Den normalen Reisebegleiter standardmäßig Kennungen persistieren zu lassen, liegt
außerhalb des Umfangs.

## Aufnahmemodi und Grenzen

Der Standardmodus ist **Advertisements aufzeichnen**. Er zeichnet von Android
gelieferte Advertisements auf, ohne eine GATT-Verbindung zu öffnen.

**Ausgewählten Bus inspizieren** ist eine separate, ausdrückliche Aktion für ein
autorisiertes Testfahrzeug. Sie verbindet, entdeckt Services, liest allowlistete
Daten und trennt. Read-only-Verbindungen nutzen weiterhin Fahrzeugressourcen und
können die Verbindung eines anderen Clients beeinflussen.

Ein optionaler Modus **Entdeckte Busse inspizieren** erfordert eine ausdrückliche
Aktivierung auf Sitzungsebene und eine autorisierte Zielmenge. Seine Vorgaben sind
eine Verbindung gleichzeitig, ein Versuch pro beobachteter Adresse pro Sitzung und
ein Verbindungs-Timeout von zehn Sekunden. Wiederholung erfolgt manuell.

Kein Modus sendet Stop-, Hilfe-, Türsignal-, Fahrt-, Authentifizierungs-,
Kopplungs- oder andere Steuerbefehle. Kein Modus ruft die drei
`/busaccess/`-Aktionsendpunkte auf. Kein Modus schreibt Characteristics oder
Deskriptoren. Benachrichtigungsabonnements sind ausgenommen, weil sie normalerweise
einen Deskriptor-Write erfordern.

Die App prüft keine beliebigen nahen Telefone oder Wearables. Ein optionaler
ungefilterter Scan kann Buskandidaten identifizieren, die der aktuelle Filter
übersieht. Nichtkandidaten-Payloads bleiben flüchtig und werden nicht persistiert.
Unklassifizierte Kandidaten erhalten die ausdrückliche Bezeichnung **Unbekannter
Buskandidat** und manuelle Beibehaltung.

"Jedes Paket" bedeutet jedes relevante Scanergebnis, das Android an diese App
liefert. Es bedeutet keine vollständige Funkaufnahme. Android kann Ergebnisse
filtern, zusammenfassen, kürzen oder auslassen. Die App kann den Verkehr einer
anderen App oder die Backend-zu-Bus-Verbindung nicht aufzeichnen.

## Inhalt der Debug-Seite

Der Einstiegspunkt ist **Profil, Debug, Bus capture** in einem Debug-Build.
Produktions-Builds aktivieren die Sammlung nicht standardmäßig.

Die Sitzungssteuerung sind **Aufnahme starten**, **Aufnahme stoppen**, **Notiz
hinzufügen** und **Export**. Die Seite zeigt Berechtigungsstatus, Bluetooth-Status,
Sitzungsdauer, Anzahl empfangener Ereignisse, Anzahl persistierter Ereignisse,
Anzahl verworfener Ereignisse, Speicherverbrauch und den letzten erfolgreichen
Flush.

Der Browser bietet zwei ordnerartige Ansichten:

- **Nach Linie**: Linie, beobachtetes Busprofil, dann die Sichtungen dieses Busses
  für die ausgewählte Linie.
- **Nach Bus**: beobachtetes Busprofil, dann Linien- und Kurshistorie mit
  zeitgestempelten Sichtungen.

Unaufgelöste Werte bleiben unter **Unbekannte Linie**, **Unbekannte Haltestelle**
oder **Unbekannter Buskandidat**. Fehlender Lookup-Text verbirgt nie eine
Beobachtung.

Eine Busdetailansicht hat die Abschnitte **Übersicht**, **Pakete**, **Anfragen**,
**GATT** und **Notizen**. Die Paketliste behält Duplikate und unterstützt Filter
nach Zeit, Protokoll und Parse-Ergebnis. Ein einzelnes Paket zeigt Rohbytes,
Bytelänge, dekodierte Felder und den Grund eines Parse-Fehlers.

Die Anfrageliste umfasst Verbindungsversuche, Service Discovery, allowlistete
Reads und die Lookup-Downloads dieser Debug-Funktion. Jede Anfrage verlinkt auf
ihr Ergebnis oder ihren Timeout. Sie ist keine Liste des gesamten vom Telefon
erzeugten Verkehrs.

## Roh-Advertising-Datensatz

Jedes empfangene Buskandidaten-Ergebnis wird vor dem Parsen zur Persistenz
eingereiht. Jeder Datensatz enthält die folgenden Felder, wenn Android sie
preisgibt:

- UTC-Empfangszeit, monotone Empfangszeit, Scan-Zeitstempel, Sitzungs-ID und
  Sequenznummer.
- Beobachtete Bluetooth-Adresse, Adresstyp falls verfügbar, Gerätename falls
  verfügbar und RSSI.
- Vollständige app-sichtbare Scan-Record-Bytes als Hex, Bytelänge und ein
  Payload-Hash.
- Beworbene Service-UUIDs, Service-Data-Einträge und alle Herstellerdaten-Einträge
  mit ihren Schlüsseln und Bytes.
- Verbindbarkeitszustand, Legacy-Zustand, PHY-Werte, Advertising-SID,
  Sendeleistung und Datenvollständigkeitsstatus, wo unterstützt.
- Grund der Kandidatenklassifikation, Parserversion, Parse-Ergebnis und Details zu
  Parse-Fehlern.
- Protokoll, Firmen-ID, Hardware-ID, Linien-ID, Ziel-ID, Nächster-Halt-ID, Kurs,
  Service-Flags und unbekannte Bytes.
- Aufgelöster Linien-, Ziel- und Haltestellentext sowie Hash und Version der
  Lookup-Datenbank, wenn verfügbar.

Nicht verfügbare Felder sind null, mit einem Grund, wo sinnvoll. Unbekannt ist
etwas anderes als null. Rohbytes bleiben unverändert, wenn ein späterer Parser
eine andere Interpretation erzeugt.

Wiederholte Advertisements bleiben separate Ereignisse. UI-Zusammenfassungen
dürfen Duplikate zusammenklappen, der Export dedupliziert das Ereignislog aber
nicht stillschweigend.

Simulator-Advertisements bleiben in ausdrücklich gekennzeichneten Testsitzungen
verfügbar. Sie zählen nie als Beweis für eine echte Fahrzeugsichtung.

## Busprofile und Identität

Jedes Profil hat eine generierte interne ID. Beobachtete Bluetooth-Adressen,
Protokoll- und Firmenwerte, Hardware-IDs und Sichtungen sind Belege, die an diese
ID angehängt werden.

Eine Linie ist keine dauerhafte Fahrzeugidentität. Derselbe Bus kann Linie,
Richtung, Ziel, Kurs und nächsten Halt wechseln. Eine Linie kann mehrere Busse
gleichzeitig enthalten.

Eine Bluetooth-Adresse ist eine beobachtete Kennung, kein Beweis dauerhafter
Identität. Eine Hardware-ID kann ein Modul identifizieren statt den ganzen Bus.
Wiederverwendete IDs, Adresswechsel und mehrere Module können Mehrdeutigkeit
erzeugen.

Der anfängliche Profilschlüssel ist die Sitzungs-ID und die beobachtete
Bluetooth-Adresse. Übereinstimmende Protokoll-, Firmen- und Hardware-IDs können
eine Beziehung über Adressen oder Sitzungen hinweg nahelegen. Solche Treffer
bleiben vorläufig, bis sie geprüft sind. Linien- und Haltestellentreffer allein
führen nie zu Profilzusammenführungen.

Ein Profil behält erste und letzte Sichtungen, Adresshistorie, Roh- und aufgelöste
Feldhistorie, Paketzähler, RSSI-Bereich, Verbindungshistorie, entdeckte Services,
gelesene Werte und manuelle Notizen. Kollisionen bleiben sichtbar. Manuelle
Zusammenführungen behalten ihre ursprünglichen Profil-IDs und Audit-Ereignisse.

Ordneransichten sind Indizes über Sichtungen. Sie duplizieren oder verschieben die
Quellereignisse nicht, wenn ein Bus die Linie wechselt.

## Verbindungs- und Read-Datensätze

Jede aktive Operation hat eine Operations-ID, ein Zielprofil, eine beobachtete
Bluetooth-Adresse, Start- und Endzeitstempel und eine übergeordnete Operations-ID,
wenn relevant.

Verbindungsereignisse behalten den angeforderten Modus, das unmittelbare
API-Ergebnis, wo verfügbar, den Callback-Statuscode, Verbindungszustandsübergänge,
Timeout, Ausnahme, Trennungsgrund und Bereinigungsergebnis.

Die Service Discovery behält jede gemeldete Service-, Characteristic- und
Deskriptor-UUID, einschließlich Characteristic-Eigenschaften und
Instanzkennungen, wo verfügbar.

Reads behalten die Service- und Characteristic-Kennungen, zurückgegebene Rohbytes,
Bytelänge, Callback-Status, dekodierten Wert und Dekodierfehler. Ein
Discovery-Ergebnis impliziert nie, dass ein Read gelungen ist.

Eine Inspektion liest jede Characteristic, die die Read-Eigenschaft angibt,
nacheinander, außer denen im Anfragedienst
`00001f1f-0000-1000-8000-00805f9b34fb`. Sie schreibt nie. Eine lesbare
Eigenschaft allein beweist nicht, dass das Lesen einer unbekannten Characteristic
keine Nebenwirkungen hat, daher wird jeder Read protokolliert, bevor er gesendet
wird, und ein abgelehnter Read stoppt die anderen nicht.

Authentifizierungsanforderungen und Kopplungsaufforderungen werden als blockierte
Inspektionsergebnisse aufgezeichnet. Der Recorder umgeht die Authentifizierung
nicht und fährt nicht in einen Challenge-Response-Austausch fort.

Jeder Versuch schließt seinen GATT-Client bei Abschluss, Fehler, Abbruch oder
Timeout. Aufnahme stoppen bricht ausstehende Inspektionen ab und schließt
Verbindungen. Der Recorder wiederholt nicht in einer engen Schleife.

## Netzwerkdatensätze

Nur Anfragen der Debug-Funktion sind enthalten. Jedes Ereignis zeichnet Methode,
bereinigte URL, Operations-ID, Start- und Endzeit, HTTP-Status, Antwortlänge,
Antwort-Hash und Fehlerdetails auf.

Die für eine Sitzung genutzte Lookup-Datenbank wird einmal in den Export kopiert,
mit Hash und Herkunft. Das bewahrt die Namensauflösung nach Cache-Verdrängung oder
einer späteren Datenbankaktualisierung.

Autorisierungsheader, Cookies, API-Schlüssel, Kontotoken und unabhängiger
App-Verkehr sind ausgenommen. Kein privater App-Schlüssel wird aus dem
Original-APK kopiert.

## Dauerhaftes Log und Export

Die Quelle der Wahrheit ist eine append-only UTF-8-JSON-Lines-Datei. Jede
vollständige Zeile ist ein Ereignis. Sie ist in einem Texteditor lesbar und kann
zum Wiederaufbau der Profilindizes wiedergegeben werden.

Jedes Ereignis hat `schemaVersion`, `sessionId`, `sequence`, `eventId`, `type`,
`timestampUtc`, `elapsedRealtimeNanos`, optional `profileId`, optional
`operationId` und ein `data`-Objekt.

Ereignistypen umfassen Sitzungsstart und -stopp, Advertisement-Empfang,
Parse-Ergebnisse, Identitätsbeobachtungen, Verbindungslebenszyklus,
Discovery-Ergebnisse, Read-Anfragen und -Ergebnisse, Netzwerkanfragen und
-ergebnisse, Notizen, Berechtigungsänderungen, Scanfehler, Writer-Fehler und
Aufnahmelücken.

Der Ereignis-Writer nutzt eine begrenzte Warteschlange und schreibt außerhalb des
UI-Threads. Sein Ziel-Flush-Intervall ist eine Sekunde. Stopp und Export fordern
einen sofortigen Flush an. Die UI unterscheidet empfangene, eingereihte,
geschriebene und geflushte Ereignisse.

Nach einem Absturz liest die Wiederherstellung vollständige Zeilen und meldet eine
unvollständige letzte Zeile. Ein Absturz kann ungeflushte Ereignisse verlieren.
Warteschlangenüberlauf erhöht einen sichtbaren Verwurfzähler und erzeugt ein
Lückenereignis, wenn das Schreiben wieder anläuft. Speichererschöpfung stoppt die
Sammlung mit einem sichtbaren Fehler. Keine der beiden Bedingungen wird als
vollständige Aufnahme gemeldet.

Dateien liegen in app-privatem persistentem Speicher, nicht im Cache und nicht in
Logcat. Das vorgeschlagene Sitzungsverzeichnis ist
`files/bluetooth-captures/{sessionId}/`. Seine vorgeschlagenen Dateien sind
`events.jsonl`, `session.json`, `profiles.json` und ein optionales Verzeichnis
`lookups/`. Diese Pfade sind ein vorgeschlagener Vertrag, keine bestehenden
Ausgaben.

`profiles.json` ist ein abgeleiteter Schnappschuss. `session.json` zeichnet
App-Version, Gerätemodell, Android-Version, Scaneinstellungen, erteilte
Berechtigungen, aktivierte Modi, Sitzungsgrenzen, Dateihashes und
Abschlusszustand auf. Es schließt persistente Telefonkennungen aus.

Der Export bietet die einfache Datei `events.jsonl` und ein ZIP mit der ganzen
Sitzung. Ein Export während der Aufnahme enthält nur ein konsistentes geflushtes
Präfix und zeichnet seine Cutoff-Sequenz auf. Die Aufnahme kann nach diesem Cutoff
weiterlaufen.

Die Debug-UI verlangt ausdrückliche Zustimmung, bevor rohe Bluetooth-Adressen
behalten werden. Exporte enthalten Fahrzeugbeobachtungen und möglicherweise
Ortsnotizen. Sie bleiben lokal, bis der Nutzer sie teilt. Automatische Uploads und
Analytics sind für Aufnahmeinhalte deaktiviert.

GPS-Aufnahme ist standardmäßig aus. Ein optionaler Ortsmodus zeichnet
Berechtigungsstatus und Genauigkeit auf. Eine manuell eingegebene Haltestellennote
ist als Notiz gekennzeichnet, nicht als aus dem Bus dekodierte Haltestelle.

Aufnahmedateien sind von der automatischen Sicherung ausgeschlossen. Aufbewahrung
und Löschung sind ausdrückliche Nutzeraktionen. Löschung ist nicht Teil des
Exports.

## Sitzungslebenszyklus

Der Scan gehört zur Aufnahmesitzung, nicht zur Komposition des Debug-Bildschirms.
Ein Paket zu öffnen oder Tabs zu wechseln stoppt die Sammlung nicht.

Betrieb im Hintergrund und bei gesperrtem Bildschirm erfordern einen geeigneten
Android-Dienst und Geräteprüfung. Der bestehende Ortungsdienst belegt nicht, dass
diese Anforderungen erfüllt sind. Wenn Hintergrundaufnahme ungeprüft ist, nennt
die Seite diese Einschränkung und der Feldtest hält die App sichtbar.

Die Sitzung zeichnet Bluetooth-Änderungen, Berechtigungsänderungen, Scanfehler,
Aussetzung, Prozessneustart und fortgesetzte Sammlung als getrennte Ereignisse
auf. Ein Neustart erzeugt eine neue Sitzung mit einem Verweis auf die unterbrochene
Sitzung.

Referenzen: [Android-Hinweise zu BLE im Hintergrund](https://developer.android.com/develop/connectivity/bluetooth/ble/background)
und [GATT Discovery und Reads](https://developer.android.com/develop/connectivity/bluetooth/ble/transfer-ble-data).

## Abnahmekriterien für den ersten Feld-Build

- Starten und Stoppen einer Sitzung erzeugt eine nichtleere, exportierbare
  JSONL-Datei ohne Backend-Verbindung.
- Rohbytes überleben einen Parserfehler, eine unaufgelöste ID und ein unbekanntes
  Protokoll.
- Zwei Geräte auf derselben Linie bleiben getrennt. Ein Linienwechsel bleibt im
  selben Profil des beobachteten Geräts.
- Eine fehlende Hardware-ID verhindert weder Paketbeibehaltung noch Export.
- Jede begonnene Inspektion hat ein aufgezeichnetes Ergebnis, Abbruch oder Timeout
  und schließt ihren GATT-Client.
- Die Aufnahme führt keine Characteristic-Writes, Deskriptor-Writes oder Kopplung
  aus. Sie sendet nie automatisch Fahrgaststeueranfragen.
- Ausdrückliche Busaktionen nutzen
  `POST https://service.ivanto.de/busaccess/stopRequest`, `doorsignalRequest` oder
  `serviceRequest` mit einem JSON-Feld `btMac`.
- Echte Aktionen erfordern eine laufende Aufzeichnung, ein innerhalb von 30
  Sekunden gesehenes Advertisement, beworbene Unterstützung und Bestätigung der
  Berechtigung für diesen Bus. Weitere Taps in derselben Busansicht senden direkt.
- Demoaktionen simulieren Antworten ohne Netzwerkzugriff. Echte Aktionen haben ein
  Timeout von 10 Sekunden und keine automatischen Wiederholungen oder
  Weiterleitungen. Jeder abgeschlossene oder fehlgeschlagene Versuch kann manuell
  ohne Abkühlzeit oder Versuchslimit wiederholt werden. Es kann nur eine Anfrage
  gleichzeitig laufen.
- Das Log speichert URL, Body, HTTP-Code, Antwortbody und Ergebnis jeder Aktion.
  Antworten sind auf 64 KiB begrenzt und als gekürzt markiert. Nur HTTP-Erfolg mit
  `status: true` zählt als Serverbestätigung, nicht als Beweis der Ausführung am
  Fahrzeug.
- Jede Anfrage wird vor der Übertragung geflusht. Erfolgs- und Fehlerergebnisse
  werden geflusht, bevor ein weiterer Versuch freigegeben wird. Schließen oder
  Neustarten der App löscht diese Datensätze nicht. Der Downloads-Spiegel erhält
  dieselben Ereignisse, wenn aktiviert. Ausdrückliche Löschung von Sitzungen oder
  Exporten kann die jeweiligen Kopien dennoch entfernen.
- Ein Read-Fehler behält den ursprünglichen Callback-Status und erscheint nicht als
  erfolgreicher Read.
- Der exportierte Lookup-Schnappschuss reproduziert die aufgelösten Namen der
  Sitzung ohne Netzwerkzugriff.
- Ein Force-Stop hinterlässt früher geflushte Ereignisse lesbar. Die
  Wiederherstellung meldet jeden unvollständigen Rest.
- Warteschlangenüberlauf und Speicherfehler erzeugen sichtbare Zustände
  unvollständiger Aufnahme.
- Der Nutzer kann vom physischen Telefon exportieren und das Log vor der Fahrt auf
  einem anderen Gerät öffnen.
- Wegnavigieren vom Debug-Bildschirm erhält die Aufnahme. Unterstützung bei
  gesperrtem Bildschirm ist entweder geprüft oder ausdrücklich als nicht
  unterstützt markiert.

## Umfang nach dem Feldtest

Der erste Build priorisiert Rohaufnahme, dauerhaften Export, Profile und
Fehlersichtbarkeit. Vollständige Protokoll-18-Dekodierung, ausgefeiltes
Identitätsmatching und autorisierte automatische Inspektion sind getrennte Arbeit,
wenn sie einen zuverlässigen Aufnahme-Build verzögern.

Die Feldaufnahme kann belegen, welche Pakete dieses Telefon empfängt und welche
autorisierten Reads gelingen. Sie kann keine flottenweite Kompatibilität,
garantierte Zustellung, vollständige Funkaufnahme oder physische Ausführung von
Fahrgaststeuerbefehlen beweisen.
