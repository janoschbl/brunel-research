# Phase-2-Plan: vom Crash-Orakel zur Shell

[English](../en/rce-phase-2-plan-2026-11-07.md) · [Deutsch](rce-phase-2-plan-2026-11-07.md)

Datum: 7. November 2026
Ziel: `78:C4:0E:C0:2B:D7`, Profil `p-8eef9540`, BlueZ 5.78
Basis: [`rce-field-run-2026-11-07.md`](rce-field-run-2026-11-07.md)
Status: Die Zustellung ist bewiesen. Ziel-Offset, Canary-Zustand und Adressen sind es nicht.

## Fazit

Das Telefon reicht mir, um den Action-Overflow zuzustellen und den Absturz-Offset
zu messen. Es reicht **nicht** für die EIR-Namensstufe und ist der schwächste der
verfügbaren Hosts für einen ROP-Versuch. Ein Raspberry Pi mit dem ASUS USB-BT500
oder das Laptop mit demselben Dongle ist die richtige Plattform für die Chain.
Ein originaler ESP32 WROOM reicht nicht. Ein ESP32-S3 ist optional, und nur für
die EIR-Stufe.

Das fehlende Stück ist Zielwissen, nicht Hardware. Bis Offset und Adresssatz
existieren, beweist jeder Host nur einen Absturz.

## Was der Exploit tatsächlich tut

Es gibt zwei getrennte Bugs. Verwechsle sie nicht.

### 1. Action-Overflow (`0x1f20`), der Kontrollfluss-Kandidat

1. Scanne nach der Bus-Advertisement und mach einen Fingerprint. Der nützliche
   Marker ist der Name `BlueZ 5.78` plus das Service-Paar `0x1f1f` / `0x1f20`.
2. Verbinde dich. `0x1f20` ist `PROPERTY_WRITE` und wird von der Vendor-App
   behandelt, nicht von `bluetoothd`.
3. Handle MTU 517 aus und schreibe einen 512-Byte-Wert. Das ist ein normaler
   GATT-Write; er braucht kein Pairing, keine Zugangsdaten und keine Vendor-App.
4. Der Vendor-Handler kopiert den Wert in einen festen Stack-Puffer. Wenn die
   Kopie unbegrenzt ist, überschreibt der Rest gespeicherte Kontrolldaten,
   einschließlich der gespeicherten Rücksprungadresse.
5. Ich erkenne die Überschreibung aus der Ferne als Advertising-Stille: Der
   App-Prozess stirbt, die Verbindung bricht ab und die Advertisement verschwindet.
6. Die Nutzlast ist nicht zufällig Füllmaterial. `brunel rce` sendet ein
   De-Bruijn-Muster, um den Offset zu finden, oder eine ARMv7-ret2libc-Chain:

   ```text
   pop {r0, r4, pc} ; <command pointer> ; filler ; system ; "cmd"
   ```

   Eine erfolgreiche Chain führt `system(cmd)` in der Vendor-App aus.

Im Labor habe ich Zustellung und Kontrollfluss bewiesen, nicht das Ziel.
`action-e2e.sh` sendet einen echten 512-Byte-ATT-Write über BlueZ 5.78 an einen
256-Byte-Handler und bekommt `PWNED-GATT`; `action-rop.sh` führt dieselbe Chain
auf x86-64 und ARMv7 aus. Am echten Ziel ist derselbe Write weiterhin nur eine
**Absturzsonde**, bis Offset und Adressen landen.

### 2. EIR-Namensoverflow (CVE-2026-80186), das billige DoS

Ein 253 Byte langer ungültiger UTF-8-Lokalname überschreibt `char utf8_name[250]`
um drei Bytes. Bei Stock 5.78 landen die drei Bytes in einer Ausrichtungslücke
und die Schleife stoppt an einem Nullbyte, also wird keine Rücksprungadresse
überschrieben. Ein gehärteter Build oder ein ASan-Build bricht ab. Das ist ein
DoS, nicht der RCE-Pfad.

Das Telefon kann das nicht senden: Androids Advertising-API schreibt
strukturierte AD-Felder und sendet Service-Daten, keinen rohen `0x09`-Namen. Der
Linux-Client und die ESP32-S3-Firmware können es.

## Schweregrad, ehrlich

| Eigenschaft | Wert |
|---|---|
| Vektor | BLE in der Nähe, kein Kabel, kein Pairing |
| Reichweite | Feld-RSSI-Median −57 dBm, −94 bis −46 dBm; Dutzende Meter an einer Haltestelle |
| Auth | Keine beobachtet; die Berechtigung liegt serverseitig und ist weiterhin unbestätigt |
| Interaktion | Keine am Ziel |
| Nebenläufigkeit | Eine Verbindung gleichzeitig; Fahrgäste können dazwischenkommen |
| Wirkungskreis | Ein Modul, nicht die Flotte; der Bus fährt weiter |
| Reife | Im Labor bewiesene Chain; fernes Crash-Orakel; noch kein Ziel-Absturz |
| Erholung | Ein 512-Byte-Absturz trennt Bluetooth, bis die App neu startet |

Ungefähre CVSS 3.1, mit dem Vorbehalt, dass es eine Schätzung ist:

- Fernes DoS heute: `AV:A/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` → etwa **6.5**.
- Wenn die Chain in einem root-Prozess landet: `AV:A/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H`
  → etwa **8.4**.

Es ist kein Wurm, nicht internetweit und keine bewiesene RCE. Es ist
interessant, weil es unauthentifiziert, deterministisch und von einem Gehweg aus
erreichbar ist.

## Was ich damit tun kann

Heute:

- den Fahrwegtext, die Haltestellenliste, die PnP-ID, die Firmware-Revision und
  das GATT-Inventar lesen;
- echte Fahrgast-Actions senden: `0x01` Stop, `0x02` Einstieg, `0x03` Tür, `0x04` Fahrt;
- die Vendor-App abstürzen lassen und das Modul bis zum Neustart von Bluetooth nehmen;
- Builds fingerprinten und Module vergleichen.

Mit einer gelandeten Chain:

- Kommandos als Benutzer der App ausführen und diesen Benutzer mit `id` erfahren;
- `/proc/self/maps` exfiltrieren und das Vendor-Binary und `libc` dumpen, was den
  nächsten Lauf vom Brute-Force zu einer sauberen Chain macht;
- den advertisierten Namen oder den Fahrwegtext als sichtbares Beacon ändern;
- einen Fuß in der Tür halten und möglicherweise das HTTPS-Action-Backend und die
  Fahrzeugschnittstellen erreichen, mit denen die App schon spricht.

Nicht mit dieser Chain: Kernel-Kompromittierung, OTA-Persistenz oder
flottenweite Ausbreitung.

## Was ich zum Auslösen brauche

1. Physische Nähe zu einem verwundbaren Modul (RSSI besser als etwa −70 dBm).
2. Ein BLE-5-Central mit MTU 517 und einem 512-Byte-Write-Pfad.
3. Den gemessenen Absturz-Offset `L` aus der Leiter.
4. Den Canary-Zustand: Wenn `L-4` überlebt, sitzt ein Stack-Canary bei `L`.
5. Adressen: `libc`-Basis, `system`, ein `pop {r0, ...}`-Gadget und die Stelle,
   an der die Kommandozeichenkette landet. Diese kommen aus einem Dump,
   `/proc/self/maps` oder Brute-Force.
6. Den Prozessbenutzer und das Erholungsverhalten nach einem Absturz.
7. Erlaubnis, fahrgastsichtbaren Zustand zu ändern, und eine Haltestelle, die
   nicht unmittelbar bevorsteht.

## Hardware-Entscheidung

| Host | Action-Sonde / Leiter | 512-Byte-Chain | EIR-Namensstufe | Urteil |
|---|---|---|---|---|
| Pixel 9a | Ja, mit App-Arbeit | Möglich, geringste Zuverlässigkeit | Nein | Nur Feld-Orakel |
| Raspberry Pi + ASUS USB-BT500 | Ja | Ja, validierter Pfad | Ja | **Empfohlen** |
| Laptop + ASUS USB-BT500 | Ja | Ja | Ja | Am besten, wenn mitgeführt |
| ESP32 WROOM | Nein (BLE 4.2) | Nein | Nein | Reicht nicht |
| ESP32-S3 | Kein GATT-Client in der Firmware | Nein | Ja | Optionales EIR-Beacon |

### Pixel 9a

Nützlich: trägt die App bereits, BLE 5, kann MTU 517 anfragen, kann `0x1f20`
enumerieren und beschreiben und hat die Leiter und die 250-ms-Präsenzmessung.

Grenzen:

- Android kann keinen rohen 253-Byte-Namen senden, die EIR-Stufe ist also nicht verfügbar.
- Keine rohen ATT-PDUs und kein `btmon`. Timing und Opcode-Wahl gehören zu Android.
- Lange Writes hängen vom Prepare-Write-Verhalten des Stacks ab; das muss
  validiert werden, bevor ich mich darauf verlasse (siehe die App-Arbeit unten).
- Die App muss im Vordergrund bleiben; Android kann sie drosseln oder beenden.
- Es gibt noch keine Chain-Sonde: Die App kann De Bruijn senden, aber nicht
  `--offset`, `--system` oder `--gadget` setzen.

Urteil: Nutze es für Fingerprint, Hello und die Leiter, wenn der Pi nicht da ist.
Mach es nicht zum primären Chain-Host.

### Raspberry Pi

Der validierte Pfad: rohes HCI, exaktes EIR, MTU-Kontrolle, `btmon`,
JSON-Ausgabe und eine Offset-Schleife. Das eingebaute `hci0` ist BLE 4.2, der
ASUS USB-BT500 an `hci1` ist also Pflicht. Trag ihn im Rucksack, binde ihn über
den Telefon-Hotspot an oder steuere ihn über SSH. Die Feldtest-Kommandos stehen
schon im Basisdokument.

Urteil: Das ist der Host für Phase 2.

### ESP32 WROOM

Ein originaler ESP32-D0WDQ6 ist BLE 4.2. Er kann das S3-Buscheck-Projekt nicht
ausführen und die 259-Byte-Extended-Advertisement nicht senden. Er ist kein
Controller für diesen Exploit. Flashe ihn nur als Demo-Ziel neu, und selbst dann
bleibt die Advertisement bei 31 Bytes.

Urteil: Nicht nötig.

### ESP32-S3

BLE 5, 259-Byte-Extended-Advertisement, führt `firmware/s3-buscheck/` aus. Das
macht ihn zu einem guten Rucksack-Beacon für das EIR-DoS und für Übungen am
virtuellen Pi-Bus. Er hat keinen GATT-Client, kann die Action-Stufe also nicht
ausführen.

Urteil: Optional, nur EIR.

## Was ich jetzt brauche

### A. App-Härtung vor dem nächsten Feldtest

- Eine `action_hello`-Sonde hinzufügen, die **nur** `0x01` sendet. `action_known`
  sendet `0x01` bis `0x04` und ändert die Anzeige viermal; die Leiter sollte von
  einer Ein-Action-Basis starten.
- Ein strukturiertes `bench_write`-Ereignis pro Write hinzufügen: numerischer
  `status`, `props`, `handle`, `mtu`, `length`, erste 32 Bytes in Hex, `op` und
  `ok`. Das Sondenergebnis allein ist kein ausreichender Beleg.
- `writeLong` explizit machen: Wenn der Wert `mtu - 3` übersteigt,
  `beginReliableWrite` / `executeReliableWrite` mit `mtu - 5`-Blöcken nutzen,
  statt anzunehmen, dass der Android-Stack Prepare-Write macht. Den Command-Pfad
  für passende Werte behalten.
- Eine Chain-Sonde mit den Feldern `offset`, `profile`, `system`, `gadget` und
  `command` hinzufügen, damit das Telefon die letzte Stufe ausführen kann.
- Den 201-Reconnect und Cache-Reset behalten. Zwei 201er als Stoppbedingung behandeln.

### B. Bench-Gate

Vor dem Berühren eines Busses ausführen:

```sh
lab/scripts/action-e2e.sh
lab/scripts/action-rop.sh
cd research && .venv/bin/python -m pytest tests/test_rce.py
./gradlew :exploit:testDebugUnitTest :exploit:assembleDebug
```

Dann das neue APK auf dem Pixel installieren und die neue Sonde gegen den
virtuellen Pi-Bus ausführen. Ein grünes Labor mit rotem Feldpfad ist weiterhin ein No-go.

### C. Zielwissen

- Am besten: ein geparktes Modul oder eine Depot-Einheit. `/proc/self/maps`, die
  Vendor-App und `libc` dumpen und die Build-Flags und den Prozessbenutzer
  lesen. Das beantwortet alles.
- Ohne Einheit: Die Leiter liefert `L`; der `L-4`-Wiederholungslauf
  unterscheidet einen Canary; dann den `libc`-Seitenoffset mit einem bekannten
  sicheren Kommando brute-forcen. Erwarte einen Absturz pro Fehlversuch und
  plane Erholungszeit ein.
- `id` und die Maps zuerst aufzeichnen, wenn eine Chain landet.

### D. Feldausrüstung

Telefon mit dem neuen APK, Powerbank, Pi + ASUS-Dongle + Strom, Ethernet- oder
Hotspot-Anbindung, `btmon`-Aufzeichnung, Notizbuch und das Basis-Runbook.
Aktiviere das Android-HCI-Snoop-Log vor dem Losfahren.

## Feldplan, der Reihe nach

Jede Stufe hat ein Gate. Überspringe nichts bei einem Teilergebnis.

| Gate | Aktion | Bestanden | Stopp |
|---|---|---|---|
| 0 | Bench-Gate oben; HCI-Snoop an; Aufzeichnung läuft | Alles grün | Irgendetwas rot |
| 1 | Nur Fingerprint, `--no-leak --dry-run` oder App-`fingerprint` | `BlueZ 5.78`, `0x1f20`-Props `0x08` | Adresse oder Name geändert |
| 2 | `0x01`-Hello, einmal | Write-Status 0, Fahrgastanzeige reagiert | Zwei Fehlschläge oder zweimal 201 |
| 3 | Leiter mit Prepare, von 1 aufwärts | Erstes `L` mit Advertising-Stille | Keine Erholung in 60 s |
| 4 | `L-4` nach der Erholung | Überlebt → Canary bei `L`; stürzt ab → gespeichertes LR bei `L` | Nach zwei Versuchen unklar |
| 5 | Erholungsprofil | `0x1f20` kommt zurück, `0x2020` antwortet noch, Ausfallzeit protokolliert | Alle Services weg |
| 6 | Nulladress-Chain bei `L` | Reproduzierbarer Absturz genau bei `L` | Absturz bei einer anderen Länge |
| 7 | Echte Chain, harmloses Kommando | Kommando beobachtbar | Drei Fehlversuche |

Stufe 6 ist die Absturzreproduktion, keine Shell. Stufe 7 wird nur mit vollem
Adresssatz versucht.

Für den Telefonpfad nutze `fingerprint` → `att_mtu` → `action_hello` →
`action_ladder`. Für den Pi nutze die exakten Kommandos in
[`rce-field-run-2026-11-07.md`](rce-field-run-2026-11-07.md). Führe die
Leiter nicht auf einem Bus aus, der gleich die Fahrgast-Haltestelle erreicht.

## Kommando-Nachweisleiter

`echo` allein ist unsichtbar: Die Standardausgabe des Daemons geht nicht über
die Luft. Nutze einen beobachtbaren Effekt:

1. `killall bluetoothd`: eine Stille, die deutlich länger ist als der normale Absturz.
2. `hciconfig hci0 name PWNED` oder `btmgmt --index 0 name PWNED`: in der
   nächsten Advertisement sichtbar.
3. `hciconfig hci0 name "$(id)"`: kleiner Exfiltrationskanal.
4. `cat /proc/self/maps > /tmp/maps` und später eine Chain, die das in eine
   zweite Advertisement oder einen Netzwerk-Callback kopiert.

Ein Absturz plus Erholung ist ein erreichbarer Overflow. Zur RCE wird es erst,
wenn der Kommandoeffekt beobachtet wird.

## Offsets, Canary, Adressen

- Ein Absturz bei `L` und Überleben bei `L-4` bedeutet einen Stack-Canary. Der
  Canary-Wert ist unbekannt; dann sind ein Leck oder Brute-Force nötig.
- Ein Absturz sowohl bei `L` als auch bei `L-4` bedeutet, die gespeicherte
  Rücksprungadresse liegt bei `L` und es gibt keinen Canary. Das ist der leichte Fall.
- Ein nicht ausgerichtetes `L` deutet auf eine byteweise Kopie oder einen Canary
  hin; wiederhole `L-1`, `L-2`, `L-3`, `L-4` nach jeder Erholung.
- ARMv7-`system` und das Gadget brauchen das Thumb-Bit; der Kommandopointer
  bleibt gerade. Der Builder erzwingt das bereits.
- Wenn ein Dump unmöglich ist, bevorzuge einen Kommandopointer im selben Puffer
  und ein Gadget plus `system` aus einem plausiblen `libc`-Mapping. Eine Seite
  ist 4096 Bytes; brute-force zuerst diesen niedrigen Nibble-Bereich, nicht den
  ganzen Adressraum.

## Erfolg und Belege

Aufzeichnen: den JSON/WRITE-Verlauf, die numerischen Status, die exakte Länge bei
jedem Absturz, die ersten 32 Bytes, die Ausfallzeit, das Service-Inventar nach
der Erholung, den advertisierten Namen nach der Erholung, `btmon` und einen
HCI-Snoop. Ein negatives Ergebnis mit diesem Verlauf ist trotzdem ein Ergebnis.

## Sicherheit

- `0x01` ist eine echte Stop-Anforderung. Sende sie einmal.
- Ein 512-Byte-Absturz trennt Bluetooth, bis die App neu startet.
- Eine Verbindung gleichzeitig; Fahrgäste haben Vorrang.
- Stelle den Anzeigezustand wieder her, wenn es praktikabel ist.
- Ein negatives Ergebnis ist kein Nicht-Verwundbarkeitsbeweis; die Firmware
  unterscheidet sich je Modul.

## Offene Fragen

- Ist der Write auf `0x1f20` am Ziel pre-auth, oder braucht er Verschlüsselung?
  Die Hello-Stufe beantwortet das.
- Ist die Vendor-App überwacht? Wenn sie von selbst neu startet, ist die
  Erholung schnell; wenn nicht, ist ein Absturz ein längerer Ausfall.
- Nutzt der Build `-fstack-protector`? `L-4` beantwortet das.
- Welcher Benutzer führt die Vendor-App aus? `id` nach einer Chain.
- Ist ein geparktes Modul oder eine Depot-Einheit für einen Dump verfügbar? Das
  ist der Unterschied zwischen einer gemessenen Chain und einer
  Brute-Force-Kampagne.
