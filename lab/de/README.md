# Labor

[English](../en/README.md) · [Deutsch](README.md)

Reproduzierbares BlueZ-5.78-Ziel für die Bench. Zwei Wege:

- **Host-Harness**: kein Root, kein Funkgerät. Baut den verwundbaren Parser mit
  ASan und beweist CVE-2026-80186 in Sekunden.
- **Docker-Ziel**: vollständiger `bluetoothd` auf `btvirt` mit einem
  Angreifer-Controller über TCP. Braucht `/dev/vhci` und einen privilegierten
  Container.

## Host-Harness

```sh
lab/scripts/build-bluez.sh
lab/scripts/repro-eir.sh
```

`repro-eir.sh` führt den verwundbaren Parser aus, erwartet einen
ASan-Stack-Buffer-Overflow bei `name2utf8`, wendet die Upstream-Klemme an und
erwartet einen sauberen Lauf. Es gibt nur `PASS` aus, wenn beide Hälften halten.

Der primitive Harness zeigt, was der EIR-Fehler auf Stock 5.78 tatsächlich tut:
ein einfacher Build überlebt, ein ASan- oder FORTIFY-Build bricht ab. Er gibt
außerdem den geleakten Lauf aus.

```sh
lab/scripts/eir-primitive.sh
```

Der GATT-Datenbank-Harness ist getrennt:

```sh
lab/scripts/build-gatt-harness.sh
lab/build/harness/gatt_db_harness
```

## Docker

```sh
cd lab
LAB_MODE=eir docker compose up --build
```

Das Ziel stellt den Angreifer-Controller auf `127.0.0.1:9000` bereit. Vom Host
aus:

```sh
research/.venv/bin/brunel bench --transport tcp-client:127.0.0.1:9000 --level dos
```

`LAB_MODE=gatt` startet `btgatt-server` statt `bluetoothd` und die
Discovery-Schleife. Nutze es für die ATT- und GATT-Proben; nutze `eir` für den
Advertisement-Überlauf und SDP/L2CAP.

Oder führe die Bench vom Host in einem Schritt aus:

```sh
lab/scripts/run-docker-bench.sh dos
```

Logs landen in `lab/logs`.

## Telefon im Kreislauf

Zwei Skripte lassen das Telefon gegen diesen PC testen:

```sh
sudo lab/scripts/run-phone-sim.sh usb:0
sudo lab/scripts/run-eir-target.sh
```

`run-phone-sim.sh` bewirbt einen Fake-Bus mit Protokoll 18 in der echten
GATT-Form und protokolliert jeden Read und jede Aktion. Nutze es, um die App vor
einem Feldlauf zu validieren.

`run-eir-target.sh` stoppt den System-Daemon, führt den ASan-5.78-`bluetoothd`
auf `hci0` aus und startet die Discovery. Nutze es, um den EIR-Payload über Funk
zu testen. Der Android-Advertiser des Telefons sendet Service Data, keinen
vollständigen lokalen Namen, ein negatives Ergebnis hier ist also kein negatives
Ergebnis für den Fehler.

Wenn du nur einen Adapter und kein gerootetes Telefon hast, nutze den PC als
beide Seiten:

```sh
sudo lab/scripts/self-eir.sh
```

Es führt das ASan-Ziel aus, bewirbt den exakten 255-Byte-Payload über `btmgmt`
und prüft das Log auf einen ASan-Absturz. Das ist der vollständige Funkpfad auf
einem Controller.

Alle drei Skripte brauchen `sudo` und stoppen den System-Bluetooth-Daemon für die
Dauer.

## Lokal ohne Docker

```sh
lab/scripts/run-local.sh eir
```

Das braucht `sudo` für `/dev/vhci` und `socat`.

## Was das Labor beweist und was nicht

Der Harness beweist den Parserfehler im exakten 5.78-Quellcode. Das Docker-Ziel
beweist Erreichbarkeit über `bluetoothd` und den Controller. Keines beweist den
Hersteller-Build. Die Feld-Bench zeichnet den Hersteller-Fingerprint und den
Absturzzeitpunkt auf; der Bericht hält beides getrennt vom Laborergebnis.

## Kernel-Matrix

Der Kernel des Moduls ist unbekannt. `lab/kernel/` enthält die Matrix und die
QEMU-Notizen. Gehe nicht von 6.6 aus. Die L2CAP-Proben sind Best-Effort gegen
welchen Kernel das Ziel auch immer ausführt; ein negatives Ergebnis bedeutet
nur, dass der Pfad diesen Build nicht abstürzen ließ.

## Action-ROP-Beweis

`action-e2e.sh` führt den vollständigen 512-Byte-Aktionspfad gegen einen
Bumble-GATT-Server mit einem 256-Byte-Handler aus. Es startet zwei verknüpfte
`btvirt`-Controller und braucht daher kein Root und kein Funkgerät. Der Angriff
nutzt die normale `brunel rce`-Stufe und muss `PWNED-GATT` ausgeben.

`action-rop.sh` beweist die x86-64- und ARMv7-Builder gegen Handler mit festen
Puffern. ARM läuft unter `qemu-arm-static` mit der musl-Cross-Toolchain in
`/mnt/storage/offload/toolchains`.

Der Bumble-GATT-Server ist `lab/action_target.py`, der Handler ist
`lab/harness/action_vuln.c`.
