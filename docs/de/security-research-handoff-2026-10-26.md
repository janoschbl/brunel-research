# Vertrauliche technische Übergabe: Bus-Bluetooth, Brunel und BlueZ-Prüfkandidaten

[English](../en/security-research-handoff-2026-10-26.md) · [Deutsch](security-research-handoff-2026-10-26.md)

Stand: 26.10.2026 · Hauptaufnahme: 24.10.2026 · Zielgruppe: Hersteller-PSIRT und beauftragte Sicherheitsforscher

Dieses Dokument bündelt den bisherigen Gesprächskontext, den am 26.10.2026 vorhandenen Quellstand und die erneut ausgewertete Aufnahme `20261024-180855-ed53`. Es ist eine Bestandsaufnahme und ein Konzept für eine autorisierte Sicherheitsprüfung, kein fertiger Schwachstellennachweis. Es enthält weder Exploitcode noch Anweisungen zum Auslösen von Speicherfehlern an Fahrzeugen.

Die enthaltenen Geräteadressen, Zeitstempel und Backend-Routen sind für eine vertrauliche Übergabe gedacht. Vor einer öffentlichen Veröffentlichung sollten sie geprüft und gegebenenfalls pseudonymisiert werden.

## 1. Ergebnis und Anliegen

Gesichert ist Folgendes:

- Mehrere beobachtete BLE-Geräte senden den Namen `BlueZ 5.78`. Bei drei Adressen wurde dieser Name zusätzlich erfolgreich aus der GATT-Characteristic `0x2a00` gelesen.
- Dieselben drei Geräte lieferten eine PnP ID, deren Werte zum BlueZ-Upstream-Standard und zur Version 5.78 passen.
- Das Telefon kann bei diesen Geräten Services entdecken und unter anderem Ziel- und Haltestellentexte aus einer herstellerspezifischen GATT-Characteristic lesen.
- Der Export enthält 2.111 Ereignisse, darunter 1.846 Advertising-Ergebnisse, 25 GATT-Verbindungsversuche und 46 erfolgreiche Characteristic-Reads.
- Zusätzlich enthält er 15 ausdrücklich ausgelöste HTTPS-Aktionsanfragen. Zwölf protokollierte Antworten lauten `{"status":false}`; drei Anfragen enden clientseitig mit Timeout. Eine ausgeführte Fahrzeugaktion ist damit nicht belegt.

Nicht gesichert sind der genaue Hersteller-Firmwarestand, Linux-Kernel, BlueZ-Patchstand einschließlich Backports, aktive Audio-Profile, Discovery-Verhalten des Moduls, Sicherheitsanforderungen seiner Characteristics und eine konkrete ausnutzbare Schwachstelle.

**Die belastbare Meldung lautet deshalb: "Reproduzierbarer BlueZ-5.78-Fingerprint und dokumentierte BLE/GATT-Angriffsfläche; bitte produktbezogene CVE-Triage und kontrollierte Verifikation ermöglichen."** Sie lautet nicht: "Remote Code Execution am Bus bewiesen."

Eine alte Versionsnummer allein beweist keine Verwundbarkeit. Umgekehrt begründet sie ohne Patch-, Konfigurations- oder Erreichbarkeitsnachweis auch keine pauschale Entwarnung. Zeitnah sinnvoll ist eine technische Zuordnung der Kandidaten zu den tatsächlich ausgelieferten Builds.

## 2. Hintergrund und bisheriger Austausch

Nach Angaben des Meldenden wurde das Unternehmen bereits kontaktiert. Es habe erklärt, dass die Firmware noch nicht aktualisiert worden sei, die Sicherheitslücken aber unbedenklich seien. Für weitere Schritte beziehungsweise ein Testgerät mit Beispielfirmware werde konkrete Evidenz oder ein ausgearbeitetes Prüfkonzept erwartet.

Die Original-E-Mails liegen dieser Auswertung nicht bei. Diese Zusammenfassung ist daher die Schilderung des Meldenden, keine unabhängig geprüfte Aussage des Unternehmens.

Ziel des Meldenden ist eine konstruktive Sicherheitsmeldung ohne Schaden. Bisher wurden Versions-Fingerprints und normale App-Kommunikation ausgewertet; es wurde kein produktbezogener Exploitnachweis erbracht. Die Anforderung eines PoC ist keine dokumentierte Freigabe für veränderte Pakete, Fuzzing oder Störungstests im Fahrbetrieb.

## 3. Evidenzstufen und Aussagegrenzen

| Stufe | Bedeutung | Aktueller Stand |
| --- | --- | --- |
| E1 | Identifikation/Fingerprint aus normalen Antworten | Für drei Geräte durch GATT-Name und PnP ID gut belegt; weitere Namen im Advertising |
| E2 | Exakter Produktbuild enthält den ungepatchten Fehler | Nicht belegt; Herstellerquellen, Binary oder nachvollziehbare Patchliste fehlen |
| E3 | Notwendige Rolle, Konfiguration und Eingabepfad sind erreichbar | Für gewöhnliches GATT-Lesen belegt, für die CVE-spezifischen Pfade überwiegend unbekannt |
| E4 | Reproduzierbarer Speicher-/Logikfehler im passenden isolierten Build | Für das Produkt nicht durchgeführt |
| E5 | Auswirkung am isolierten Testgerät nachgewiesen | Nicht durchgeführt; kein belegter Produkt-DoS, keine belegte RCE |

Die Logs sind von meiner Android-App erzeugte Anwendungsprotokolle. Sie sind keine unabhängige Geräteattestation, kein Firmware-Dump, kein vollständiger Funkmitschnitt und kein HCI-Snoop-Log.

Ein erfolgreicher GATT-Read beweist eine lesbare Characteristic unter dem damaligen Verbindungszustand. Er beweist weder fehlende Funkverschlüsselung noch einen Authentifizierungsfehler. Ebenso ist ein Android-Verbindungsfehler kein Beweis, dass `bluetoothd` abgestürzt ist.

## 4. Was ich gebaut habe

### 4.1 Projekt und Module

Arbeitsverzeichnis:

```text
/home/janosch/.t3/projects/padermodern
```

Das Projekt heißt PaderBrunel/Brunel und ist ein inoffizieller Android-Client für PaderSprinter-Daten. Die Oberfläche verwendet Kotlin, Jetpack Compose und Material 3.

| Modul | Zweck | Android applicationId |
| --- | --- | --- |
| `app` | Normale Fahrplan-/Fahrtbegleitungs-App mit optionaler Bus-Erkennung | `dev.padermodern` |
| `capture` | Separate BusLab-/Capture-App für Aufzeichnung, GATT-Inventar, Ansicht und Export | `dev.padermodern.buslab` |

Beide Module stehen im untersuchten Quellstand auf `versionName = "1.0"`, `versionCode = 1`, `minSdk = 31`, `targetSdk = 36` und `compileSdk = 37`. Die Java-Quellkompatibilität ist 17; die Projektanleitung nennt JDK 21 als Build-Umgebung. Debug-/lokale Testartefakte sind nicht mit einer Hersteller-Firmware gleichzusetzen.

Wichtig: Der Arbeitsbaum enthält nicht eingecheckte Änderungen und neue Dateien. Der Commit

```text
850f159c22a7907f09e97a6f6babef8427ba9088
```

allein reproduziert den hier beschriebenen Stand deshalb nicht. Ein Quellcodepaket muss auch die geänderten und unversionierten Dateien enthalten. Aus `appVersion: 1.0` im Log lässt sich nicht ableiten, welcher Quellstand damals installiert war.

### 4.2 Architektur und Kommunikationswege

Es gibt drei zu trennende Wege:

1. **Advertising:** Busmodul → Android-BLE-Scanner → Decoder → Bus-/Linienanzeige.
2. **GATT-Lesen:** Telefon als GATT-Client → Busmodul als GATT-Server → Service Discovery → Characteristic-Read → Interpretation der Antwort.
3. **Aktionsanfragen:** In der Capture-App ausdrücklich ausgelöste HTTPS-Anfragen → ivanto-Backend. Das ist nicht derselbe Weg wie ein GATT-Write.

Die bestehende Dokumentation zur ursprünglichen PaderSprinter-Mobil-App 8.7.8 beschreibt zusätzlich einen direkten BLE-Schreibpfad für Fahrgastwünsche. Meine Capture-Inspektion führt solche GATT-Writes nicht aus.

Die Herstellerarchitektur wird in der bestehenden Projektdokumentation mit einem fahrzeugseitigen Datenbezug über IBIS beschrieben. Aus meiner Aufnahme folgt weder eine konkrete IBIS-/CAN-Verdrahtung noch eine über Bluetooth erreichbare Fahrzeugsteuerung. Ein kompromittiertes Bluetooth-Modul wäre nicht automatisch ein kompromittierter Fahrbetrieb.

## 5. Wie der Radar-/Scanbetrieb funktioniert

"Radar" bezeichnet hier die Anzeige erreichbarer BLE-Geräte. Es ist keine Entfernungsmessung und keine verlässliche Orts- oder Fahrzeugauthentifizierung. RSSI hängt unter anderem von Abschattung, Antennen und Umgebung ab.

### 5.1 Normale App: Fahrtbegleitung

Die Klasse `PassiveBusScanner` verwendet Androids `BluetoothLeScanner` mit einem Filter auf den Service

```text
00001f1f-0000-1000-8000-00805f9b34fb
```

und `SCAN_MODE_BALANCED`. Empfangene Scan Records werden strukturell geprüft und als Bus-Advertising dekodiert. Simulator-Advertisements werden verworfen. Die Bluetooth-Adresse dient im laufenden Prozess als Zuordnungsschlüssel; diese Scannerklasse führt selbst keine GATT-Operation aus.

Der Name "PassiveBusScanner" bedeutet nicht, dass auf Funkebene garantiert niemals Scan Requests gesendet werden. Android-Scan-Callbacks sind auch kein vollständiger BLE-Sniffer.

Die Fahrtbegleitung ordnet Beobachtungen zur ausgewählten Linie und zur GPS-/Routenlage zu. Sie verwendet unter anderem wiederholte Beobachtungen, zeitliche Gültigkeit und konservative Plausibilitätsprüfungen. GPS bleibt der Rückfallpfad. Diese Regeln reduzieren Fehlzuordnungen, sind aber keine kryptografische Echtheitsprüfung eines Busses.

Bei zum Fahrtverlauf passenden Protokoll-18-Beobachtungen kann `VehicleDataReader` zusätzliche Fahrzeugtexte lesen:

- Eine aktive GATT-Leseoperation zur selben Zeit.
- `connectGatt` mit `autoConnect = false` und LE-Transport.
- Service Discovery und ausschließlich Read von `0x2020` im Service `0x201f`.
- Im aktuellen Quellstand: 20 Sekunden Operations-Timeout, reguläre Aktualisierung nach 15 Sekunden, maximal 30 Sekunden alte Cache-Daten, Fehlerabstand 5 Sekunden, Vergessen alter Einträge nach 120 Sekunden.
- Abschluss durch Disconnect/Close, auch bei Fehler oder Timeout.
- Keine GATT-Writes, kein Notification-Abonnement und kein expliziter `createBond`-Aufruf in dieser Klasse.

Android kann Sicherheitsabläufe selbst auslösen oder bestehende Bonds verwenden. Das Fehlen eines expliziten Pairing-Aufrufs beweist deshalb keinen unverschlüsselten Link.

### 5.2 Capture-App: Scan und automatische Inspektion

Die Capture-App wird vom Nutzer als Sitzung gestartet und läuft über einen Foreground Service mit sichtbarer Benachrichtigung und Stop-Funktion. Sie fordert Bluetooth-/Standortberechtigungen an; die Hauptaufnahme nennt zusätzlich die Benachrichtigungsberechtigung.

Standardmäßig verwendet der aktuelle Code:

- `SCAN_MODE_LOW_LATENCY` und `setLegacy(false)`.
- Zwei alternative Scan-Filter: Service `0x1f1f` **oder** Manufacturer `0x7d78`. Die Filter sind nicht als gleichzeitige UND-Bedingung zu verstehen.
- Einen optionalen ungefilterten Scanmodus. Auch dann werden fremde Geräte nicht vollständig als Busprofile persistiert, sondern Kandidaten anhand Service/Manufacturer ausgewählt.
- Automatische GATT-Inspektion als gespeicherte, initial eingeschaltete Option. Die Hauptaufnahme bestätigt automatische Nur-Lese-Inspektion.

Im aktuellen `AutoInspectPolicy` stehen unter anderem Mindest-RSSI −85 dBm, Mindestabstand 10 Sekunden und Aktualisierungsabstand 30 Sekunden. Protokoll 16 wird grundsätzlich einmal pro Adresse und Sitzung inspiziert; Protokoll 18 kann bei Änderung der Datenversion oder nach Ablauf des Aktualisierungsintervalls erneut gelesen werden. Simulatoren, nicht dekodierbare Datensätze und ausdrücklich nicht verbindbare Geräte werden nicht automatisch inspiziert. Es läuft nur eine Inspektion gleichzeitig.

Diese Angaben beschreiben den aktuellen Quellstand. Die exakten damaligen Timer lassen sich nicht aus dem Versionsnamen 1.0 rückwirkend garantieren.

### 5.3 Advertising-Decoder

Die Parser prüfen zunächst die Länge der AD-Strukturen, Servicekennung und Herstellerkennung. Beobachtet beziehungsweise im Code vorgesehen sind:

| Feld | Bedeutung im aktuellen Decoder |
| --- | --- |
| Service `0x1f1f` | Kennzeichnung des BusAccess-Kontexts |
| Manufacturer `0x7d78` | Reale Bus-Kandidaten |
| Manufacturer `0x7d79` | Simulator-Kennung; in der normalen App ausgeschlossen |
| Protokoll 16 | Numerische Linien-, Ziel-, Haltestellen-, Hardware- und Kurskennungen |
| Protokoll 18 | Linienbezeichnung als Text; weitere Texte werden bei Bedarf über GATT gelesen |
| Niedrige drei Bits von Byte 4 bei Protokoll 18 | Rollierende Datenversion 0 bis 7, **keine Firmwareversion** |

Im internen Manufacturer-Datenarray einschließlich Company-ID stehen die Protokollbytes an Offset 2/3. Für Protokoll 16 werden die Kennungen ab Offset 6 jeweils als Little Endian gelesen; für Protokoll 18 prüft der Decoder die Markierung an Offset 10 und liest die Textlinie ab Offset 11. Diese Beschreibung dient der Zuordnung des vorhandenen Decoders, nicht der Konstruktion veränderter Funkpakete.

Protokoll-18-Felder, die im gemeinsamen Modell als 0 erscheinen, sind nicht automatisch tatsächlich übertragene Hardwarekennungen. Teile dieses Formats sind weiterhin unbekannt. Die Capture-App bewahrt Rohdaten auch bei unbekanntem Protokoll auf.

## 6. GATT-System und aktuelle Leseoperationen

Alle folgenden 16-Bit-Kurzformen verwenden die Basis `0000xxxx-0000-1000-8000-00805f9b34fb`. Die herstellerspezifischen Kurzformen sind hier beobachtete UUIDs, keine Behauptung einer standardisierten Bedeutung.

### 6.1 In der Aufnahme beobachtete Services der drei näher identifizierten BlueZ-Geräte

| Service | Characteristic | Beobachtete Eigenschaften / Nutzung |
| --- | --- | --- |
| `0x1800` Generic Access | `0x2a00` | READ; Gerätename, hier `BlueZ 5.78` |
| `0x1800` | `0x2a01`, `0x2aa6` | READ |
| `0x1801` Generic Attribute | `0x2a05` | INDICATE; Descriptor `0x2902` vorhanden, nicht abonniert |
| `0x1801` | `0x2b29` | READ und WRITE; hier nur gelesen |
| `0x180a` Device Information | `0x2a50` | READ; PnP ID |
| `0x201f` | `0x2020` | READ; Ziel-/Haltestellentexte |
| `0x1f1f` | `0x1f20` | WRITE; von der Capture-Inspektion nicht geschrieben |

Die Protokoll-16-Geräte mit erfolgreicher Inventarisierung zeigen einen kleineren Serviceumfang, insbesondere `0x1800` und `0x1f1f`. Ein GATT-Inventar bildet keine vollständige BR/EDR-SDP-Inventarisierung ab.

Die Capture-Inspektion verbindet, entdeckt Services und liest sequenziell die als READ markierten Characteristics; Service `0x1f1f` wird beim Lesen ausgespart. Der aktuelle Code setzt einen 30-Sekunden-Timeout und beendet die Verbindung anschließend. Er zeichnet UUIDs, Properties und Descriptor-UUIDs auf, aber liest keine Descriptor-Werte und aktiviert keine Notifications/Indications.

**Properties sind keine Sicherheitsberechtigungen.** Ein WRITE-Bit sagt nicht, ob Pairing, Linkverschlüsselung, Authentisierung oder eine Anwendungsauthentisierung verlangt werden. Umgekehrt folgt aus lesbaren öffentlichen Fahrplandaten noch keine Datenschutz- oder Zugriffskontrolllücke.

### 6.2 Textformat der Route-Characteristic

`0x2020` liefert hier UTF-8-Text mit dem Trennzeichen U+001D. Mein Parser behandelt das erste Feld als Ziel und das zweite als nächste Haltestelle; ein nachfolgendes Trennzeichen ist möglich.

Beispiel aus Ereignis 752:

```text
Characteristic: 00002020-0000-1000-8000-00805f9b34fb
Hex:            4b61756b656e626572671d4b617373656c65722053747261c39f651d
Dekodiert:      Kaukenberg<U+001D>Kasseler Straße<U+001D>
```

Andere gelesene Kombinationen sind Sennelager Infanterieweg / Westerntor und Technologiepark / Westerntor. Es handelt sich um Fahrzeug-/Routentexte, nicht um Firmwareinhalte.

### 6.3 Versionsabfragen: was bereits vorliegt und was fehlt

Im beobachteten Device Information Service wurde `0x2a50` angeboten, nicht aber Firmware Revision `0x2a26`, Software Revision `0x2a28`, Hardware Revision `0x2a27`, Model Number `0x2a24` oder Manufacturer Name `0x2a29`.

Solche Characteristics sind kein universeller Mechanismus zum Auslesen einer Linux-Firmware. Welche davon vorhanden sind, bestimmt die Implementierung. Die Standardbeschreibung erläutert ihre Bedeutung, verspricht aber nicht, dass jedes Gerät alle Werte anbietet. [Bluetooth SIG: Device Information Service](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/DIS_v1.2/out/en/index-en.html)

Ein Linux-Kernel, Paket-Patchlevel oder vollständiges Root-Dateisystem kann nicht allein durch "ein paar weitere normale GATT-Reads" ermittelt werden, wenn das Gerät diese Daten nicht bereitstellt.

## 7. HTTPS-Aktionspfad und ursprüngliche App

### 7.1 Aktueller Capture-Code

`capture/.../BusRequests.kt` kennt diese POST-Routen:

```text
https://service.ivanto.de/busaccess/stopRequest
https://service.ivanto.de/busaccess/doorsignalRequest
https://service.ivanto.de/busaccess/serviceRequest
```

Der Request-Builder übergibt eine Bluetooth-Adresse als JSON-Feld `btMac`, verwendet JSON als Content-Type und setzt `Accept: application/json`. Ein ausdrücklicher Authorization-Header ist in diesem Builder nicht enthalten. Das ist eine Quellcodebeobachtung, kein Beweis für die gesamte serverseitige Sicherheitsarchitektur.

Die aktuelle UI-/Hub-Logik verlangt eine explizite lokale Freigabe, eine laufende Aufnahme, eine aktuelle Advertisement-Beobachtung und das passende Unterstützungsflag. Sie sendet nicht automatisch beim Scan. Die lokale Freigabe ist eine Bedien-Schranke in meiner App, keine vom Server durchgesetzte Berechtigung.

Die HTTP-Implementierung verwendet 10 Sekunden Call-Timeout, keine automatischen Wiederholungen und keine Redirects. Eine Antwort gilt nur bei 2xx, nicht abgeschnittenem Body und `status:true` als angenommen. Manuelle neue Anfragen bleiben möglich.

Ein Timeout bedeutet "Ergebnis unbekannt", nicht "garantiert nicht ausgeführt". Die Aufnahme dokumentiert nicht die physische Wirkung im Fahrzeug. Ein Türfinde-/Türsignal ist insbesondere nicht gleichbedeutend mit einem Türöffnungsbefehl.

### 7.2 Abgrenzung zur ursprünglichen PaderSprinter-Mobil-App

Die bestehende Datei `docs/de/bluetooth-radar.md` beschreibt eine frühere statische Untersuchung der ursprünglichen App 8.7.8:

- Bus-Erkennung über Advertising und Lookup-Daten.
- Direkte Fahrgastwünsche über einen kurzen Schreibwert an `0x1f20`.
- Einen zusätzlichen HTTPS-Zustellweg.
- Transportabschluss beziehungsweise Serverstatus, aber keinen unabhängigen Nachweis der tatsächlichen Fahrzeugwirkung.
- Eine getrennte `BusCoreApi`-Challenge-Response-Implementierung und eine separate, in jenem Build deaktivierte MQTT-Funktion.

Diese frühere Analyse wurde für die vorliegende Übergabe nicht durch erneute APK-Dekompilierung unabhängig reproduziert. Insbesondere darf die getrennte Challenge-Response-Implementierung nicht ohne Nachweis als Schutz des Radar-/BusAccess-Pfads angenommen werden. Genauso darf aus dem Fehlen eines solchen Nachweises keine bestätigte Umgehung abgeleitet werden.

## 8. Was, wie und wo geloggt wird

### 8.1 Erfassung und Ereignisschema

Die Capture-App speichert JSON Lines: eine JSON-Struktur je vollständiger Zeile. Ereignisse enthalten unter anderem `schemaVersion`, `sessionId`, fortlaufende `sequence`, `eventId`, `type`, UTC-Zeit, `elapsedRealtimeNanos` und gegebenenfalls `profileId` und `operationId`.

Advertising-Ereignisse können enthalten:

- Geräteadresse, Gerätename, RSSI, Android-Scanzeit und rohe Scan-Record-Bytes als Hex.
- Service-UUIDs, Service Data und Manufacturer Data.
- Connectable-/Legacy-Status, PHY-/SID-/TxPower-/DataStatus-Angaben, soweit Android sie liefert.
- Decodergebnis oder Decoderfehler, Parser-Version und Lookup-Zuordnung.
- Einen verkürzten Datenhash zur Zuordnung.

GATT-Ereignisse dokumentieren Verbindungsanforderungen, Callback-Status, Serviceinventar, Read-Anforderungen und Read-Antworten mit UUID, Status, Bytes und Länge. HTTP-Ereignisse dokumentieren Methode, URL, JSON-Body, Content-Type, Antwortstatus/-body oder Ausnahme. Request-Header werden im Export nicht vollständig erfasst.

Nicht aufgezeichnet werden ein vollständiger ATT-/L2CAP-/HCI-Paketstrom, Controller-Firmware, Kernelmeldungen des Busmoduls, dessen Prozessabstürze oder ein gesicherter Pairing-/Verschlüsselungszustand.

### 8.2 Speicherorte auf Android

Maßgeblich ist im aktuellen Code `app.noBackupFilesDir/bluetooth-captures`, typischerweise:

```text
/data/user/0/dev.padermodern.buslab/no_backup/bluetooth-captures/<sessionId>/
    events.jsonl
    session.json
    profiles.json
    lookups/Padersprinter.sqlite
```

Der genaue Android-Pfad ist systemabhängig. Es handelt sich um App-Privatspeicher. Die App setzt `allowBackup=false`.

Zusätzlich gibt es im aktuellen Code:

- Optionalen JSONL-Spiegel über MediaStore unter `Download/Brunel/<sessionId>-events.jsonl`; initial eingeschaltet.
- ZIP-Export nach Downloads beim Abschluss, wenn der Spiegel aktiviert ist.
- Teilbare Exportdateien unter `cacheDir/exports`; bei ZIP-Export zusätzlich `export.json` mit dem Export-Cutoff.
- Geordneten Schreibpfad mit begrenzter Warteschlange von 4.096 Einträgen und periodischem Flush ungefähr im Sekundentakt.

`dropped = 0` bedeutet, dass der entsprechende App-Zähler keinen verworfenen Scan-Eintrag gemeldet hat. Es garantiert weder vollständigen Funkempfang noch, dass Android jedes Advertisement geliefert hat. Hashwerte sichern die Vergleichbarkeit der vorliegenden Bytes, nicht deren unabhängige Herkunft oder eine gerichtsfeste Beweiskette.

Die Profilkennung wird aus Sitzungskennung und Adresse abgeleitet. Da die Rohadressen ebenfalls enthalten sind, ist der Export nicht anonym.

### 8.3 Import, Replay und ältere Dokumentation

Der aktuelle Import kann frühere ZIP-Sitzungen einlesen und Rohdaten mit einer neueren Parser-Version erneut dekodieren. Daraus entstehen abgeleitete Sitzungen, unter anderem mit `-p2`-Kennung und Herkunftsverweis. Ereignis-IDs und Hashwerte können sich dadurch ändern.

**Primäre Evidenz bleibt das unveränderte Original-ZIP.** Eine neu dekodierte Sitzung ist eine Auswertung, nicht derselbe Originaldatensatz.

Die Dateien `bluetooth-capture-spec.md` und `bluetooth-field-test.md` enthalten teilweise historische Planungsstände. Aussagen wie "noch nicht implementiert", ein reiner Passivbetrieb, ältere Timeout-/Speicherpfade oder pauschal ausgeschlossene Aktionsendpunkte passen nicht vollständig zum heutigen Code und zur Hauptaufnahme. Für diese Übergabe haben Originalaufnahme und konkret benannter Quellstand Vorrang.

## 9. Hauptaufnahme und überprüfte Ergebnisse

### 9.1 Primärdatei und Integrität

Ursprünglicher Dateiname:

```text
20261024-180855-ed53 (1).zip
```

Lokaler Speicherort:

```text
/home/janosch/.t3/userdata/attachments/b7091dbb-86b6-4014-941e-2098a2867b82-9c950062-9395-43b6-b992-08ed169c0c8e-zip.zip
```

ZIP-Größe: 106.199 Bytes. SHA-256:

```text
42566fb65365997b8cf12c013195c7ef361c5c6fe50c67c7adfbc8fd631542a4
```

Inhalt unter `20261024-180855-ed53/`:

| Datei | Unkomprimierte Größe | Zweck |
| --- | ---: | --- |
| `events.jsonl` | 1.937.497 Bytes | Primärer Ereignisstrom |
| `session.json` | 652 Bytes | Sitzungsmetadaten und Hashwerte |
| `profiles.json` | 4.255 Bytes | Abgeleitete Geräteübersicht |
| `lookups/Padersprinter.sqlite` | 36.864 Bytes | Verwendeter Linien-/Ziel-/Haltestellen-Lookup |
| `export.json` | 89 Bytes | Exportzeit und Cutoff |

SHA-256 von `events.jsonl`:

```text
766d78c172d78570e74e86946f4d0f26ab713daf2b1e980ea77ceadf0f9aeb73
```

SHA-256 des Lookup-Snapshots:

```text
3464797e5e8c838aa95f12c6f1054c37809b4c9a9c9eb990e79a07339008cf0e
```

Das Archiv enthält keinen Bus-Firmware-Dump, keinen Kernel-Build, kein Hersteller-Root-Dateisystem, keinen vollständigen Bluetooth-Mitschnitt und keine APK.

### 9.2 Zeit und Erfassungsgerät

Metadaten-Zeitraum: 24.10.2026, `16:08:55.413471Z` bis `16:37:52.694818Z`, entsprechend ungefähr 18:08:55 bis 18:37:52 MESZ.

Erstes Ereignis: `16:08:55.452Z`; letztes Ereignis: `16:37:52.689Z`. Die Ereignisnummern laufen von 1 bis 2.111. Der Export wurde nach Aufnahmeende mit Cutoff 2.111 erstellt.

Erfassungsgerät laut Log: Google Pixel 9a, Android SDK 37, Capture-App 1.0, `demo:false`. **Android SDK 37 beschreibt das Telefon, nicht das Betriebssystem des Busmoduls.**

### 9.3 Ereigniszahlen

| Typ | Anzahl |
| --- | ---: |
| `advertisement` | 1.846 |
| `connect_requested` | 25 |
| `connection_state` | 22 |
| `gatt_services` | 13 |
| `read_requested` | 46 |
| `gatt_read` | 46, jeweils Status 0 |
| `http_request` | 15 |
| `http_response` | 12 |
| `http_error` | 3 |
| `op_start` / `op_result` | je 40 |
| `session_start` / `session_stop` / `lookup_snapshot` | je 1 |

Von den 15 HTTPS-Anfragen betreffen elf `stopRequest` und vier `doorsignalRequest`; eine `serviceRequest`-Anfrage ist in dieser Sitzung nicht enthalten. Alle zwölf protokollierten Antworten haben HTTP 200, `status:false` und `accepted:false`. Drei Anfragen haben clientseitige Timeout-Ausnahmen.

Die 40 Operations-Ergebnisse verteilen sich auf 13 `ok`, 24 `error` und 3 `timeout`. Ein `error` kann hier auch eine reguläre negative Backend-Antwort darstellen; die Kategorien sind kein Geräte-Crashindikator.

Es gibt 74 als `unknown_protocol` klassifizierte Advertising-Ergebnisse. Das ist zunächst eine Decodergrenze meiner App, kein Nachweis fehlerhafter Firmware oder eines Speicherfehlers auf dem Ziel.

In dieser Sitzung sind keine GATT-Writes protokolliert. Die Capture-Inspektion implementiert keine solchen Writes. Die Sitzung insgesamt war wegen aktiver GATT-Reads und HTTPS-Aktionsanfragen dennoch **nicht rein passiv**.

### 9.4 Geräteinventar

Die Tabelle enthält elf beobachtete Bluetooth-Adressen, nicht elf zweifelsfrei verschiedene Fahrzeuge. Adressen und Namen sind ohne zusätzliche Bindung keine verlässlichen Identitäten. Die Linienangaben sind dekodierte Beobachtungen, keine dauerhaften Fahrzeugzuordnungen.

| Adresse | Profil-ID | Ads | Format / beobachtete Linie | Versionshinweis |
| --- | --- | ---: | --- | --- |
| `00:07:80:D1:90:BA` | `p-c27f3649` | 1.347 | P16 / 2; Hardware-ID 835 | GATT-Name leer; Version unbekannt |
| `00:07:80:D1:91:58` | `p-ad62ff2c` | 15 | P16 / 6; Hardware-ID 781 | GATT-Name leer; Version unbekannt |
| `78:C4:0E:A0:3F:F5` | `p-377c50fb` | 17 | P18 / 1 | `BlueZ 5.78` im Advertising und GATT; PnP ID passend |
| `78:C4:0E:A0:44:67` | `p-eb328fbe` | 95 | P18 / 1 | `BlueZ 5.78` im Advertising und GATT; PnP ID passend |
| `78:C4:0E:A0:44:F5` | `p-aa36dbca` | 4 | P18 / 12 | `BlueZ 5.78` im Advertising |
| `78:C4:0E:C0:2E:1F` | `p-cbc715bf` | 25 | P18 / 4 | `BlueZ 5.78` im Advertising |
| `78:C4:0E:C0:2E:E1` | `p-b9d1bb74` | 215 | P18 / 7 | `BlueZ 5.78` im Advertising und GATT; PnP ID passend |
| `78:C4:0E:C0:2F:05` | `p-2a0026ae` | 23 | P18 / 5 | `BlueZ 5.78` im Advertising |
| `78:C4:0E:C0:2F:CB` | `p-9808becf` | 30 | P18 / 2 | `BlueZ 5.78` im Advertising |
| `88:6B:0F:4B:C0:2C` | `p-a7aa5ab9` | 1 | P16 / P+R; Hardware-ID 886 | Version unbekannt |
| `94:E6:86:E5:10:06` | `p-0a6255ac` | 74 | P18-Kennung, Decoder `unknown_protocol` | Name `ivi`; Version unbekannt |

Es wäre falsch, alle beobachteten Geräte pauschal als BlueZ-5.78-Installationen zu melden.

### 9.5 Konkrete Belegstellen für BlueZ 5.78

Für Profil `p-377c50fb`:

| Ereignis | UTC | Characteristic | Rohwert |
| --- | --- | --- | --- |
| 742 | 24.10.2026, 16:23:37.206 | `0x2a00` | `426c75655a20352e3738` → `BlueZ 5.78` |
| 750 | 24.10.2026, 16:23:37.472 | `0x2a50` | `026b1d46024e05` |
| 752 | 24.10.2026, 16:23:37.611 | `0x2020` | Ziel-/Haltestellentext, siehe Abschnitt 6.2 |

Weitere Name-/PnP-Read-Paare: Ereignisse 1219/1235 und 1942/1951 für `p-eb328fbe` sowie 1450/1462 und 1869/1883 für `p-b9d1bb74`.

Die PnP-Bytes lassen sich wie folgt einordnen:

- Vendor ID Source `0x02`: USB-ID-Namensraum.
- Vendor `0x1d6b`: Linux Foundation.
- Product `0x0246`: BlueZ-Standardwert.
- Product Version `0x054e`: entspricht der BlueZ-Bildung `(major << 8) | minor` für 5 und dezimal 78.

Diese Standardwerte werden im öffentlichen BlueZ-5.78-Code aus `VERSION` gebildet. Das ist eine starke zusätzliche Fingerprint-Stütze, aber keine kryptografische Attestation und insbesondere keine Identifikation des tatsächlichen Hardwareherstellers durch die USB-Vendor-ID. Werte können konfiguriert oder verändert werden. [BlueZ 5.78: Initialisierung in src/main.c](https://github.com/bluez/bluez/blob/5.78/src/main.c)

## 10. CVE-Triage: was konkret weitergemeldet werden sollte

Die folgenden Einträge sind **Prüfkandidaten**, keine Liste bestätigter Produktlücken. Die Priorisierung bewertet den nächsten Erkenntnisgewinn, nicht einen bereits ermittelten CVSS-Wert des Fahrzeugs.

Zunächst sollten Herstellerbuild, Backports und aktive Rollen geklärt werden. Danach sind der Gerätenamen-Parser und tatsächlich aktive Kernel-/BLE-Pfade vorrangig. Audio- und lokale D-Bus-Themen sind nur bei passenden Voraussetzungen hochzustufen.

### 10.1 CVE-2026-80186: Gerätenamen-/EIR-Parser

**Fehlerklasse:** Stacküberlauf in `name2utf8`, `src/eir.c`; laut Advisory DoS und mögliche Codeausführung bei Discovery.

**Bezug zu 5.78:** Der öffentliche Tag 5.78 enthält den unbegrenzten Kopierpfad. Die vollständige Funktion hat allerdings einen vorgeschalteten UTF-8-Pfad. Ein vereinfachter Nachbau nur des Kopiervorgangs belegt deshalb nicht automatisch den vollständigen Parser und schon gar nicht eine Funk-Ausnutzung der Produktfirmware.

**Erforderlich:** Das Modul muss fremde Namen über den betroffenen Empfangs-/Discovery-Pfad verarbeiten. Dass es selbst `BlueZ 5.78` sendet oder meinem Telefon einen GATT-Namen liefert, genügt nicht. Das Advisory beschreibt insbesondere Extended Inquiry Response bei Discovery; der Fixtext erwähnt auch Advertising Reports. Für eine behauptete BLE-Erreichbarkeit müssen die konkrete Datenzuführung sowie Controller-/Kernel- und Paketgrenzen nachgewiesen werden. Keine pauschale Gleichsetzung mit gewöhnlichem Legacy-BLE-Advertising.

**Konzeptioneller Nachweis:** Hersteller-Code gegen den Fix vergleichen; erlaubten Empfangspfad mit normalen Labordaten instrumentieren; danach vollständigen Originalparser offline mit Speicherüberwachung prüfen und einen gepatchten Kontrollbuild gegenüberstellen. Ein vereinfachtes ASan-Beispiel ist nur ein Fehlerklassenbeleg, kein Produkt-PoC.

**Status:** Gut begründeter Upstream-Codekandidat; Herstellerpatch und Erreichbarkeit offen. Für diese Geräte weder DoS noch RCE nachgewiesen.

Quellen: [Upstream-Advisory](https://github.com/bluez/bluez/security/advisories/GHSA-68h6-5qgp-3975), [Code 5.78](https://github.com/bluez/bluez/blob/5.78/src/eir.c), [Fix 381b5d0](https://github.com/bluez/bluez/commit/381b5d0d208972586282116d333865ba93b8dec2), [CVE-/Paketzuordnung](https://security-tracker.debian.org/tracker/CVE-2026-80186).

### 10.2 Linux-Kernel: unabhängig von der BlueZ-Version prüfen

Eine BlueZ-Version bestimmt keine Kernelversion. Folgende Kandidaten gehören in eine **bedingte Inventarprüfung**, nicht als bestätigte Lücken in den Befundkopf:

| CVE | Thema / mögliche Auswirkung | Noch nötige Produktzuordnung |
| --- | --- | --- |
| `CVE-2022-42896` | L2CAP Use-after-free; die beschriebenen Pfade betreffen mögliche Codeausführung beziehungsweise Speicherpreisgabe | Kernelstand, Fix/Backport und konkreter LE-/BR/EDR-Pfad |
| `CVE-2022-42895` | L2CAP-Speicherpreisgabe, unter anderem Kernel-Pointer | Betroffene Funktion, Konfiguration und Protokollvoraussetzungen |
| `CVE-2024-53144` / `CVE-2024-8805` | BR/EDR-Just-Works-Bestätigungslogik | Ob BR/EDR-Pairing angeboten wird und der Kernelpatch fehlt |
| `CVE-2020-12351` | BleedingTooth: A2MP/L2CAP-Typverwechslung mit möglicher RCE | Entsprechend alter, ungepatchter Kernel und erreichbare Funktion |
| `CVE-2020-12352` | BleedingTooth: Informationsabfluss im Kernel-Bluetooth-Pfad | Kernel-/Funktionszuordnung |
| `CVE-2020-24490` | BleedingTooth: HCI-/Extended-Advertising-Speicherfehler | Kernel, Controllerfähigkeit und tatsächlicher Empfangspfad |

Bei `CVE-2022-42896` dürfen Auswirkungen der verschiedenen Funktionen nicht pauschal auf den LE-Pfad übertragen werden. `CVE-2022-42895` ist für sich kein RCE-Nachweis. Der Linux-CNA-Datensatz zu `CVE-2024-53144` referenziert `CVE-2024-8805` ausdrücklich; die beiden Bezeichnungen sollten nicht als zwei unabhängig belegte Produktlücken gezählt werden.

Geeignete erste Evidenz wäre die exakte Kernel-Build-ID mit Patchnachweisen und Konfiguration. Ein beschädigtes Paket gegen ein reales Fahrzeug ist dafür weder erforderlich noch hier vorgesehen.

Quellen: [CNA 2022-42896](https://github.com/CVEProject/cvelistV5/blob/main/cves/2022/42xxx/CVE-2022-42896.json), [Red Hat 2022-42895](https://access.redhat.com/security/cve/cve-2022-42895), [Linux-CNA 2024-53144 mit Bezug auf 2024-8805](https://github.com/CVEProject/cvelistV5/blob/main/cves/2024/53xxx/CVE-2024-53144.json), [Fix b25e11f](https://github.com/torvalds/linux/commit/b25e11f978b63cb7857890edb3a698599cddb10e), [Red Hat: BleedingTooth](https://access.redhat.com/security/vulnerabilities/BleedingTooth).

### 10.3 CVE-2026-80185: SDP-XML über lokalen D-Bus

**Fehlerklasse:** Typverwechslung im SDP-XML-Parser bei `RegisterProfile(ServiceRecord)`; entsprechende Muster wurden im öffentlichen 5.78-Code identifiziert.

**Voraussetzung:** Ein lokaler Prozess muss den betreffenden D-Bus-Aufruf mit eigenen Profildaten ausführen dürfen. Eine BLE-Verbindung oder ein GATT-Read verschafft diese lokale Berechtigung nicht automatisch.

**Auswirkung:** Belastbar ist hier zunächst lokaler DoS. Der weitergehende Upstream-Titel zu Root-Codeausführung beziehungsweise einem angrenzenden LE-Peer darf nicht ungeprüft übernommen werden: Red Hat stellt ausdrücklich fest, dass die vorgelegte Evidenz keine Codeausführung belegt.

**Konzeptioneller Nachweis:** D-Bus-Policy und lokale Konten/Prozesse prüfen; Parser ausschließlich in einer isolierten Kopie des passenden Builds untersuchen. Keine Testregistrierung in einem laufenden Fahrzeug.

**Status:** Lokaler, konfigurationsabhängiger Kandidat, kein nachgewiesener Remote-Bluetooth-Angriff.

Quellen: [Red Hat/CNA-Einordnung](https://access.redhat.com/security/cve/cve-2026-80185), [Upstream-Advisory](https://github.com/bluez/bluez/security/advisories/GHSA-7mmr-gwqx-vc34), [Fix 985e643](https://github.com/bluez/bluez/commit/985e643d78b09afc81d606bc0a08581fc05b1b15).

### 10.4 Audio-Kandidaten: nicht aus der Busfunktion ableitbar

Ein akustisches Türfindesignal beweist weder A2DP noch AVRCP oder LE Audio. Das Signal könnte vollständig lokal erzeugt werden. Die beobachtete GATT-Serviceliste beweist solche Profile weder positiv noch ersetzt sie eine vollständige Rollen-/SDP-Prüfung.

| CVE | Fehler / diskutierte Auswirkung | Unverzichtbare Voraussetzung | Bezug zum bisherigen Stand |
| --- | --- | --- | --- |
| `CVE-2026-19774` | A2DP-Verarbeitung entfernter Stream-Endpunkte; Stacküberlauf, mögliche Codeausführung | Aktiver A2DP-Pfad und Möglichkeit, einen passenden fremden Peer zu koppeln | Verdächtige `store_remote_sep`-/`load_remote_sep`-Muster im öffentlichen Tag 5.78; Produktrolle unbekannt |
| `CVE-2026-85218` | AVRCP-Player-Settings-Antwort; Schreibzugriffe außerhalb von Stackpuffern, mögliche Codeausführung | Passende AVRCP-Controller-Rolle, BR/EDR-Verbindung und tatsächliche Abfrage | Entsprechender Code auch in 5.78; kein Nachweis am Produkt |
| `CVE-2026-75032` | AVRCP-GetFolderItems-Längenprüfung; Out-of-bounds-Read, DoS, möglicher Heap-Informationsabfluss | AVRCP-Browsing und Verbindung/Interaktion mit passendem Peer | Betroffene Parsermuster in 5.78; Produktpfad unbekannt |

Konzeptioneller Nachweis: zuerst die Rolle und einen regulären Ablauf mit einem eigenen ungefährlichen Peer bestätigen; erst danach den Originalparser offline beziehungsweise im isolierten Labor prüfen. Ein bloß vorhandener Lautsprecher genügt nicht zur Priorisierung.

Quellen: [19774: Beschreibung und Voraussetzungen](https://security-tracker.debian.org/tracker/CVE-2026-19774), [19774: Fix 912f5ef](https://github.com/bluez/bluez/commit/912f5efb0dd9bb08e408d33371a57182c5678aef), [85218: Advisory](https://github.com/bluez/bluez/security/advisories/GHSA-m2vx-pw5f-rc8v), [85218: Fix b21c216](https://github.com/bluez/bluez/commit/b21c216d580cf303681bfe9eab60a5414d8b6cc0), [75032: CVE](https://security-tracker.debian.org/tracker/CVE-2026-75032), [75032: Fix bd89896](https://github.com/bluez/bluez/commit/bd8989620ed6e80755f06cfdb18f5b4a3913493c), [Folgekorrektur 5808814](https://github.com/bluez/bluez/commit/58088149872d014684a582fdb7ad01a5180c9bc5).

### 10.5 Weitere LE-Audio-Advisories ohne hier gesicherte CVE-Zuordnung

**GHSA-9683-2chf-hfw9: BAP/BASE-Parser:** Das Advisory beschreibt einen Stacküberlauf beim Verarbeiten von Broadcast-Audio-Metadaten. Ein aktiver BAP-Broadcast-Sink kann entsprechende Eingaben laut Bericht ohne Pairing empfangen. Notwendig sind aber genau dieser Profil-/Empfangspfad sowie passende Experimental-, Kernel-ISO- und Controllerunterstützung.

Im öffentlichen 5.78-Code enthalten `bap_sink_get_allocation` und `bap_sink_match_allocation` das beschriebene unzureichend begrenzte Kopieren. Advisory-Metadaten (`<=5.76`, keine gepatchte Version, niedrige Einstufung) und Beschreibung (auch spätere Stände, höhere Schwere) widersprechen sich. Deshalb nicht einfach "5.78 betroffen" oder "ab 5.77 behoben" behaupten.

Quellen: [BASE-Advisory](https://github.com/bluez/bluez/security/advisories/GHSA-9683-2chf-hfw9), [BAP-Code 5.78](https://github.com/bluez/bluez/blob/5.78/src/shared/bap.c).

**GHSA-7wjj-8mrm-jhw4: BASS-Client-Parser:** Das Advisory beschreibt einen Heapüberlauf beim Parsen fremder Broadcast-Receive-State-Daten. Ziel des beschriebenen Angriffs ist ein BlueZ-Host, der selbst als BASS-GATT-Client zu einem fremden Server verbindet. Das ist die umgekehrte Anwendungsrolle zu meinem Telefon, das die Route vom Bus-GATT-Server liest. Laut Advisory muss der experimentelle BASS-Pfad aktiviert sein.

Das auffällige Allokations-/Mehrfacheintragsmuster findet sich auch im öffentlichen 5.78-Code. Auch hier sind Versions- und Schweregradmetadaten widersprüchlich. Meine Aufnahme belegt weder BASS noch die notwendige Clientrolle des Moduls.

Quellen: [BASS-Advisory](https://github.com/bluez/bluez/security/advisories/GHSA-7wjj-8mrm-jhw4), [BASS-Code 5.78](https://github.com/bluez/bluez/blob/5.78/src/shared/bass.c).

Für beide gilt: Konfiguration zuerst klären. Nur bei aktivem Pfad werden sie zu vorrangigen Laborkandidaten. Keine CVE-Nummer erfinden und keine öffentliche Severity ungeprüft als Produktbewertung ausgeben.

### 10.6 Ältere, profilabhängige Kandidaten aus der bisherigen Recherche

Diese Einträge bleiben im Anhang, damit sie nicht verloren gehen. Sie sind keine zusätzlichen bestätigten Funde:

| CVE | Profil / Fehlerklasse | Weiteres Vorgehen |
| --- | --- | --- |
| [CVE-2023-44431](https://security-tracker.debian.org/tracker/CVE-2023-44431) | AVRCP-Speicherüberlauf, mögliche Codeausführung nach Verbindung mit fremdem Gerät | Rolle, genauen Hersteller-Code und Fixlage prüfen |
| [CVE-2023-51596](https://security-tracker.debian.org/tracker/CVE-2023-51596) | PBAP-Heapüberlauf, mögliche Codeausführung | Nur bei aktivem PBAP/OBEX-Pfad priorisieren |
| [CVE-2023-51580](https://security-tracker.debian.org/tracker/CVE-2023-51580) | AVRCP-Attributlisten, Out-of-bounds-Read | Aktive Rolle und konkreten Parser zuordnen |
| [CVE-2023-51589](https://security-tracker.debian.org/tracker/CVE-2023-51589) | AVRCP-Medienelemente, Out-of-bounds-Read | Auch mögliche Überschneidung mit neueren Parsermeldungen prüfen |
| [CVE-2023-51592](https://security-tracker.debian.org/tracker/CVE-2023-51592) | AVRCP-Medienordner, Out-of-bounds-Read | Nicht ungeprüft als unabhängigen Zusatzbefund zählen |
| [CVE-2023-51594](https://security-tracker.debian.org/tracker/CVE-2023-51594) | OBEX-Verarbeitung, Out-of-bounds-Read | Nur mit nachgewiesenem Dienst und betroffener Implementierung |

Die bisherige Prüfung umfasst keinen vollständigen, reproduzierbaren Produkt-Codevergleich für jeden dieser älteren Einträge. Offene Distributions-Tracker-Einträge sind ein Recherchehinweis, kein Firmwarebefund.

### 10.7 Auszuschließende oder gesondert zu behandelnde Treffer

| Eintrag | Warum nicht als bestätigte 5.78-Produktlücke melden? |
| --- | --- |
| `CVE-2021-3588` | Upstream-Korrektur bereits ab 5.56. In 5.78 ist auch die vorgelagerte Fixed-Length-GATT-Datenbankprüfung zu berücksichtigen; ein isolierter Callback ohne eigene Offsetprüfung beweist keine Regression. |
| `CVE-2021-43400` | Alte GATT-Use-after-free-Korrektur bereits in 5.62; ohne Herstellerregression kein tragfähiger Treffer gegen unverändertes 5.78. |
| `CVE-2023-27349` | AVRCP-Korrektur bereits in 5.67. |
| `CVE-2023-50229` / `CVE-2023-50230` | PBAP-Korrekturen bereits in 5.70. |
| `CVE-2023-45866` | HID-/HIDP-Fall; nicht aus dem beobachteten BLE-Routenservice ableitbar. Nur bei aktiver HID-Rolle den konkreten Fix-/Backportstand prüfen. |
| `CVE-2026-105460` | Betrifft `btmon` beim Parsen manipulierter Aufzeichnungen. Kein normaler `bluetoothd`-Remote-Pfad; gegebenenfalls Risiko der Analysewerkzeuge. |

Quellen: [SUSE 2021-3588](https://www.suse.com/security/cve/CVE-2021-3588.html), [BlueZ-5.78-GATT-Datenbank](https://github.com/bluez/bluez/blob/5.78/src/gatt-database.c), [vorgelagerte GATT-DB-Prüfungen](https://github.com/bluez/bluez/blob/5.78/src/shared/gatt-db.c), [BlueZ-CVE-Tracker mit individuellen Einträgen](https://security-tracker.debian.org/tracker/source-package/bluez).

Zusätzlich wurden lokale Advertising-Monitor-Hinweise unter [GHSA-hhgc-hfgf-8m4x](https://github.com/bluez/bluez/security/advisories/GHSA-hhgc-hfgf-8m4x) beziehungsweise [GHSA-rfcf-9fw3-m9qp](https://github.com/bluez/bluez/security/advisories/GHSA-rfcf-9fw3-m9qp) diskutiert. Es liegt dafür hier keine belastbare Zuordnung zur Produktkopie vor. Lokale D-Bus-Monitorregistrierung ist nicht mit dem Empfang eines Funk-Advertisements gleichzusetzen.

### 10.8 Patchstände richtig interpretieren

Upstream-Versionen, Debian-Paketrevisionen und Hersteller-Firmwareversionen sind verschiedene Größen. Beispielsweise sind `5.87-2`, `5.87-3` und `5.87-4` Distributionsrevisionen; sie sind keine BlueZ-Upstream-Releases mit diesen Namen.

Ein pauschaler Rat "auf 5.87 aktualisieren, dann ist alles behoben" wäre aus der Kandidatenliste nicht ableitbar. Entscheidend sind die konkret enthaltenen Korrekturen, nicht nur ein numerisch höherer Banner. Ein Hersteller kann einen Fix auf 5.78 zurückportieren und den Namen beibehalten.

## 11. Prüfbereiche jenseits bekannter CVEs

Diese Punkte sind Hypothesen für eine autorisierte Produktprüfung. Sie haben hier keine eigene CVE und sind noch keine Befunde.

### 11.1 Autorisierung der Aktions-Characteristic

Offen ist, welche Sicherheitsanforderungen für `0x1f20` gelten und welche Wirkung ein akzeptierter Wunsch hat.

Ein sinnvoller Labornachweis würde eine dokumentierte Soll-Regel gegen die tatsächliche Durchsetzung vergleichen: etwa ob eine als geschützt definierte Aktion von einem nicht berechtigten Testclient akzeptiert wird. Dafür wären Controller-/GATT-Sicherheitszustand, Serverentscheidung und Wirkung an einem Dummy-Ausgang gemeinsam zu protokollieren.

Ein WRITE-Property oder der öffentlich zugängliche Originalclient genügt nicht. Haltewünsche können absichtlich für alle Fahrgäste vorgesehen sein. Erst eine verletzte Sicherheitsgrenze macht daraus einen Autorisierungsbefund.

### 11.2 Backend-Objektberechtigung und Missbrauchsschutz

Der Client adressiert das Backend über `btMac`. Zu klären sind unter anderem Objektbindung, erlaubter Anwendungsfall, Authentisierung, Näheprüfung, Wiederholungs-/Missbrauchsschutz und Server-zu-Modul-Zustellung.

Ein BOLA-/Zugriffskontrollnachweis wäre nur sinnvoll, wenn eine definierte Berechtigungsgrenze besteht und mit Testkonten sowie zwei Dummy-Objekten eine unzulässige Überschreitung gezeigt wird. Dafür sind Staging oder Hersteller-Testobjekte vorgesehen, keine Flottenadresssuche oder Lasttests gegen die Produktions-API.

Der aktuelle Export beweist keine solche Überschreitung: Er enthält negative Antworten und unbekannte Timeout-Ergebnisse, aber keine belegte unberechtigte Ausführung.

### 11.3 Advertising-Echtheit und falsche Buszuordnung

Die aktuelle App verwendet beobachtete IDs, Text, Adresse, Signalstärke und Routenplausibilität. Diese Merkmale sind für sich keine kryptografische Herkunftsbestätigung.

Die theoretische Frage ist, ob ein fremdes oder fehlerhaftes Advertisement eine falsche Fahrgastanzeige oder Zuordnung auslösen könnte. Ein sicherer Erstnachweis erfolgt mit lokalen Replay-Fixtures oder einem eigenen, klar markierten Simulator in einer isolierten Umgebung. Er belegt zunächst einen Client-/Protokoll-Vertrauensbefund, nicht die Übernahme eines echten Busses.

Keine Nachahmung realer Busidentitäten im öffentlichen Fahrbetrieb und keine Weiterleitung von Testaktionen an echte Fahrzeuge.

### 11.4 Eigener Route-/GATT-Server und Updatekette

Die Implementierung des herstellerspezifischen Dienstes ist unbekannt. Offene Reviewfragen sind Eingabelängen, Zustandsautomaten, Verbindungsabbrüche, Ressourcenlimits, Prozessrechte, Trennung von Bluetooth und fahrzeugseitigen Schnittstellen sowie Signierung und Rollback-Schutz von Updates.

Ein eigenständiger Fehler in diesem Code wäre nicht automatisch eine BlueZ-CVE. Ohne Firmware beziehungsweise Herstellerquellen kann ich ihn weder bestätigen noch sinnvoll ausschließen. Aus Signalen wie unbekanntem Decoderformat oder einem Timeout folgt kein Memory Overflow.

## 12. Wie ein belastbarer, möglichst schonender Nachweis aussehen kann

### 12.1 Warum ein "harmloses Beweispaket" nicht allgemein existiert

Ein Versions-Read weist eine Version nach. Eine normale Antwort kann auch ein Verhalten oder eine aktivierte Funktion belegen. Sie beweist aber nicht automatisch, dass eine fehlerhafte Speichergrenze im ausführbaren Produkt erreichbar ist.

Bei Speicherfehlern kann schon das bloße Auslösen des Fehlers einen Dienst abstürzen lassen, auch ohne Shellcode oder weitere Ausnutzung. "Ich lese nur" oder "ich will nichts ausnutzen" macht veränderte Parser-Eingaben nicht automatisch ungefährlich.

Die Beweiskette besteht aus mindestens drei Teilen:

1. Der konkrete Produktbuild enthält den ungepatchten Fehler.
2. Die erforderliche Rolle und Eingabe erreichen diesen Code unter realistischen Produktbedingungen.
3. Eine dokumentierte Sicherheitsgrenze beziehungsweise Speichersicherheit wird verletzt; die tatsächlich belegte Auswirkung wird separat benannt.

Ein Upstream-ASan-Bericht kann Teil dieser Kette sein. Er ersetzt nicht den Nachweis, dass mein Herstellergerät denselben Code ausführt.

### 12.2 Vorschlag für die Forscher: stufenweise Laborevidenz

| Stufe | Erwartetes Artefakt | Begrenzung |
| --- | --- | --- |
| Inventar | Firmware-/BlueZ-/Kernel-Build-ID, SBOM, Backports, Startoptionen | Keine veränderten Funkeingaben nötig |
| Statische Zuordnung | Diff oder nachvollziehbare Binary-/Quellcodezuordnung zum Fix | Fehlende Fixstelle allein sagt noch nichts über aktive Erreichbarkeit |
| Reguläre Erreichbarkeit | Trace eines normalen Ablaufs mit eigenem Testpeer | Keine Fehlerauslösung; dokumentiert nur den Pfad |
| Offline-Regression | Originalparser des passenden Builds unter ASan/UBSan, gepatchter Kontrollbuild | Vollständige Vorprüfungen erhalten; keine künstlich vereinfachte Ersatzfunktion als Produktbeweis |
| Isolierter End-to-End-Test | Reproduktion am freigegebenen Gerät, getrennt von Fahrzeug/Produktionsbackend | Nur wenn die Fragestellung das verlangt und die Freigabe es umfasst |
| Auswirkungsbericht | Tatsächlich beobachteter DoS, Informationsabfluss oder Autorisierungsfehler | DoS nicht als RCE, Modulzugriff nicht als Fahrzeugkontrolle ausgeben |

Für Kernel-Speicherfehler sind entsprechende Kernel-Diagnostik und eine isolierte Testumgebung nötig. Für D-Bus-Fragen sind die tatsächlichen lokalen Rechte entscheidend. Für Audio-Fehler muss der relevante Rollenablauf vor dem eigentlichen Fehlernachweis bestätigt sein.

Ein guter Regressionstest dokumentiert Build-ID, Konfiguration, vollständigen Aufrufpfad, erwartetes und beobachtetes Verhalten, Stacktrace beziehungsweise Sanitizer-Befund sowie das Verhalten nach Einspielen des Fixes. Er benötigt keine waffenfähige Exploitkette.

### 12.3 Sicherheitsrahmen

Für weitere aktive Prüfungen sollten mindestens schriftlicher Scope, freigegebene Geräte/Firmware, erlaubte Protokolle, Zeitfenster, Abbruchkriterien und Ansprechpartner vorliegen.

Vorgesehen wäre ein Testgerät mit isolierten beziehungsweise simulierten Fahrzeugausgängen und ohne Verbindung zu produktiver Fahrzeugsteuerung. Funkreichweite beziehungsweise Abschirmung und Backend-Ziele müssen kontrolliert sein.

Nicht vorgesehen sind Fuzzing im Fahrbetrieb, Crash-Tests an eingesetzten Modulen, unbekannte Steuerbefehle, Änderungen an Flottenparametern, Produktions-API-Missbrauch, unkontrollierte Wiederholungen oder ein Pivot zu IBIS/CAN. Für dieses Dokument wurden keine neuen Anfragen an Busmodule oder das Produktionsbackend durchgeführt.

## 13. Was vom Hersteller benötigt wird

Für eine technische Antwort auf "betroffen oder unbedenklich?" wären folgende Angaben hilfreich:

- Produkt-/Modultyp und Zuordnung der beobachteten Adressen zu Hardware-/Firmwareständen.
- Firmware-Build-ID, Veröffentlichungsdatum und Hash; BlueZ-Paket-/Commitstand einschließlich Backportliste.
- Linux-Kernelrelease, Herstellerpatchstand und relevante Bluetooth-Konfiguration.
- Bluetooth-Controller und Controller-Firmware.
- Build-/Startoptionen von `bluetoothd`, aktivierte Plugins, Experimental-/Kernel-Experimental-Optionen und tatsächliche Prozessrechte.
- Unterstützte BLE-/BR/EDR-Rollen, eigenes Discovery-/Scanverhalten, A2DP/AVRCP/PBAP/OBEX/BAP/BASS/HID-Nutzung.
- GATT-Sicherheitsanforderungen und Soll-Autorisierung für die herstellerspezifischen Characteristics.
- Sicherheitsmodell des HTTPS-Aktionspfads, Bedeutung der negativen Antworten und Vorgehen zur Zuordnung der Timeout-Anfragen.
- Für jede relevante CVE: betroffen, nicht betroffen mit technischer Begründung, behoben mit Patchreferenz oder noch in Untersuchung.
- Ein freigegebenes Testgerät beziehungsweise eine passende Firmwarekopie und ein ausdrücklich vereinbarter Labor-Scope.

Eine nachvollziehbare "nicht betroffen"-Begründung kann zum Beispiel lauten: Fehlercode nicht enthalten, Fix zurückportiert oder notwendige Rolle technisch deaktiviert und im Produkt nicht erreichbar. Eine reine Banner- oder Altersdiskussion ersetzt diese Zuordnung nicht.

## 14. Wo meine bisherigen Auswertungen und Quellen liegen

### 14.1 Bereits vorhandene lokale Berichte

```text
/home/janosch/.t3/userdata/attachments/bluez-audit-b7091dbb/bluez-befunde.html
/home/janosch/.t3/userdata/attachments/bluez-audit-b7091dbb/cve-kandidaten.md
/home/janosch/.t3/userdata/attachments/bluez-audit-b7091dbb/pruefplan.md
```

Die Dateien enthalten das frühere Loginventar, CVE-Kandidaten und einen Prüfplan. Diese neue Übergabe präzisiert beziehungsweise ersetzt widersprüchliche Kurzformulierungen durch die hier beschriebenen Evidenzgrenzen. Frühere temporäre Entpackverzeichnisse unter `/tmp` sind keine dauerhaften Übergabeartefakte.

Die absoluten Pfade in diesem Dokument zeigen auf den Rechner des Meldenden. Externe Empfänger erhalten dadurch keinen Zugriff; die betreffenden Dateien müssen tatsächlich angehängt oder über einen vereinbarten sicheren Kanal bereitgestellt werden.

### 14.2 Wichtige Quellcodedateien

Pfade relativ zur Repositorywurzel:

| Datei | Relevanz |
| --- | --- |
| `app/src/main/java/dev/padermodern/data/BusAdvertisement.kt` | Advertising- und Fahrzeugtextdecoder |
| `app/src/main/java/dev/padermodern/companion/PassiveBusScanner.kt` | Scan der normalen App |
| `app/src/main/java/dev/padermodern/companion/VehicleDataReader.kt` | Begrenzter Read von `0x2020` |
| `app/src/main/java/dev/padermodern/companion/TripCompanionService.kt` | Einbindung in Fahrtbegleitung und GPS-/Routenabgleich |
| `capture/src/main/java/dev/padermodern/capture/CaptureHub.kt` | Aufnahme, GATT-Inspektion, Aktionsfreigabe, Dateiverwaltung, Export |
| `capture/src/main/java/dev/padermodern/capture/CaptureModel.kt` | JSONL-/Advertising-Modell, Decoderstand, AutoInspectPolicy |
| `capture/src/main/java/dev/padermodern/capture/BusRequests.kt` | HTTPS-Aktionspfad und Antwortauswertung |
| `capture/src/main/java/dev/padermodern/capture/CaptureService.kt` | Android-Foreground-Service |
| `capture/src/main/java/dev/padermodern/capture/CaptureIndex.kt` | Sitzungs-/Profilansicht und Auswertung |
| `capture/src/main/java/dev/padermodern/capture/SessionImport.kt` | Import und abgeleitete Neu-Dekodierung |
| `capture/src/main/java/dev/padermodern/ui/screens/CaptureScreen.kt` | Scan-/Sitzungsoberfläche, Listen, Export |
| `capture/src/main/java/dev/padermodern/ui/screens/CaptureBusScreen.kt` | Geräteansicht und Operationen |
| `docs/de/bluetooth-radar.md` | Frühere Analyse der ursprünglichen App |
| `docs/de/bluetooth-capture-spec.md` | Capture-Konzept mit teilweise historischen Angaben |
| `docs/de/bluetooth-field-test.md` | Feldtestkontext und Vorgehensbeschreibung |

Vorhandene relevante Tests: `BusAdvertisementTest.kt`, `BusLogReplayTest.kt`, `CaptureModelTest.kt`, `CaptureLogReplayTest.kt` und `SessionImportTest.kt` unter den jeweiligen `src/test`-Verzeichnissen.

Für diese Dokumentationsaufgabe wurden die Tests nicht neu ausgeführt. Ihre Existenz ist kein Nachweis einer Schwachstelle im Busmodul.

### 14.3 Weitere vorhandene Aufnahme-Fixtures

Unter `capture/src/main/assets/fieldtest/` liegen:

```text
20261024-112233-0c1a.zip
20261024-112844-dbd7.zip
20261024-113127-0851.zip
20261024-113213-7fd9.zip
```

Diese zusätzlichen Sitzungen sind Import-/Replay-Material. Die konkreten Zahlen und Gerätebefunde in Abschnitt 9 beziehen sich ausschließlich auf die separat bereitgestellte Hauptaufnahme `20261024-180855-ed53`. Die vier Fixtures wurden nicht zu deren Zählern addiert und hier nicht erneut vollständig inhaltlich auditiert.

### 14.4 Vorhandene APKs und Quellstand-Hashes

Am 26.10.2026 lagen folgende lokale Debug-Artefakte vor:

```text
app/build/outputs/apk/debug/app-debug.apk
SHA-256: e50c7979cb50c10508891f092b5a1dce8c1e8da9aac3cbddb9ce80e8dd84776b

capture/build/outputs/apk/debug/capture-debug.apk
SHA-256: d898fa8d3e88661011a9021c16d1bdccdcc58f5460e31175646ca6c7aeb731f0
```

Die Dateizeitstempel lagen am 24.10.2026 gegen 14:31 MESZ. Weder Zeitpunkt noch Versionsname beweisen, dass exakt diese APKs bei der Hauptaufnahme installiert waren. Die APKs wurden für diese Übergabe nicht neu gebaut.

Ausgewählte SHA-256-Werte des gelesenen Arbeitsstands:

```text
PassiveBusScanner.kt
c643252a17a66d1b158c96503c0a5011e990fa99595cc48d7807f0e8e60fb65a

VehicleDataReader.kt
a0067d96b5be3c1990760c2c9fcb117bccb0f2a2f45672c24cc47365ae49c737

BusAdvertisement.kt
f86c6cad3e858346f307a877f7db2bce2f64f8a1f3f26682658ef0b6ddaafc72

CaptureHub.kt
f660752e4046c584797dab5b1be1f67a4ceb810c7f31e402fd140c5ede731063

CaptureModel.kt
2f1f6bdf2277e785e5d7dcadfb16471786cee8308f217d146bb4337c835a239c

BusRequests.kt
7f1f6471d626f06da8e5f5831dde186647cbb349446c5c60fa67069f92c417ff
```

Diese Auswahl ist kein vollständiges Source-Manifest. Vor Übergabe eines Quellcodepakets sollte dessen eigener Hash zusammen mit Commit, Arbeitsbaumänderungen und Buildanleitung festgehalten werden. Private Zugangsdaten, Signierschlüssel, personenbezogene Daten und nicht zur Prüfung gehörende Dateien gehören nicht ungeprüft in das Paket.

## 15. Reproduktion der Auswertung ohne Funk- oder Backendzugriff

Die folgenden Beispiele lesen nur die vorhandene lokale ZIP-Datei. Voraussetzung sind `unzip`, `jq` und `sha256sum`. `archive` ist gegebenenfalls an den tatsächlichen lokalen Pfad anzupassen.

```bash
archive='/home/janosch/.t3/userdata/attachments/b7091dbb-86b6-4014-941e-2098a2867b82-9c950062-9395-43b6-b992-08ed169c0c8e-zip.zip'

sha256sum "$archive"

unzip -l "$archive"

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  sha256sum

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  jq -s 'group_by(.type) | map({type: .[0].type, count: length})'

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  jq -c 'select(.sequence == 742 or .sequence == 750 or .sequence == 752)'

unzip -p "$archive" '20261024-180855-ed53/events.jsonl' |
  jq -c 'select(.type == "http_response" or .type == "http_error")'
```

Die genannte Ereigniskennung heißt im tatsächlichen JSON `sequence`, nicht `seq`.

Für einen separaten lokalen Build beziehungsweise Unit-Test nennt das Projekt Gradle-Aufgaben wie:

```bash
./gradlew :app:assembleDebug :capture:assembleDebug
./gradlew :app:testDebugUnitTest :capture:testDebugUnitTest
```

Diese Befehle wurden bei Erstellung dieser Übergabe nicht ausgeführt. Ein Build kann Abhängigkeiten herunterladen; er kontaktiert damit nicht automatisch Busmodule. Vorhandene Skripte, die Backend-Endpunkte prüfen, sind nicht Teil der hier vorgeschlagenen read-only Logauswertung.

## 16. Empfohlenes Übergabepaket und Kernaussage für die E-Mail

Für die vertrauliche Übergabe geeignet sind:

- Dieses Markdown-Dokument.
- Das unveränderte Original-ZIP mit genanntem SHA-256.
- Die drei bisherigen Auswertungsdateien aus Abschnitt 14.1 als ergänzender Kontext.
- Auf Wunsch ein bereinigter Snapshot des tatsächlichen Arbeitsstands inklusive unversionierter Dateien und Tests.
- Falls vorhanden: Originalkorrespondenz, genaue Hardwarezuordnung und eine schriftliche Testfreigabe. Diese liegen der vorliegenden technischen Auswertung noch nicht bei.

Sachliche Kernaussage:

> Ich habe einen durch Gerätename und PnP ID gestützten BlueZ-5.78-Fingerprint sowie die zugehörige BLE/GATT-Kommunikation dokumentiert. Eine ausnutzbare Schwachstelle der konkreten Firmware behaupte ich derzeit nicht. Die beigefügten Kandidaten benötigen eine Zuordnung zu Ihrem Build, Ihren Backports und den aktiven Rollen. Bitte ermöglichen Sie eine technische Prüfung beziehungsweise begründen Sie die Nichtbetroffenheit je relevantem Kandidaten. Ein isoliertes Testgerät mit passender Firmware würde einen kontrollierten Nachweis ermöglichen, ohne eingesetzte Fahrzeuge oder das Produktionsbackend zu gefährden.

## 17. Herkunft und Bearbeitungsgrenzen dieser Übergabe

Die Zusammenstellung wurde mit KI-Unterstützung durch Codex erstellt; eine zusätzliche delegierte KI-Quellenprüfung wurde für die CVE-Einordnung genutzt. Grundlage waren lokale Quellcodedateien, das Original-ZIP, vorhandene Projektberichte und verlinkte Upstream-/CNA-/Hersteller-/Distributionsquellen. KI-Unterstützung und ein öffentlicher Advisory-Eintrag ersetzen keine menschliche Produktvalidierung.

Für diese Übergabe wurden lokale Dateien und Logs gelesen sowie öffentliche Quellen abgeglichen. Es wurden keine neuen Exploits erstellt, keine zusätzlichen Funk- oder Produktions-API-Tests vorgenommen, keine Firmware aus einem Bus extrahiert und keine E-Mail versendet. Die CVE-Liste ist eine nachvollziehbare Triage des bisherigen Recherchekontexts, keine Garantie einer vollständigen Schwachstelleninventur aller unbekannten Firmwarekomponenten.
