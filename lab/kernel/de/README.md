# Kernel-Matrix

[English](../en/README.md) · [Deutsch](README.md)

Der Kernel des Moduls ist unbekannt. Die BlueZ-Version bestimmt ihn nicht.
Nimm den Fingerprint des Kernels, bevor du eine Kernel-CVE wählst.

## Reihenfolge des Fingerprints

1. Lies `/proc/version` und `/etc/os-release`, falls eine Shell existiert.
2. Ohne Shell nutzt du das GATT- und L2CAP-Verhalten nur als grobes Signal.
3. Notiere den exakten Build-String, nicht nur die Hauptversion.

## Matrix

| Kernel | L2CAP-UAF-Kandidaten | Hinweise |
|---|---|---|
| 5.10 LTS | CVE-2022-42896, CVE-2022-42895 | prüfe den Stable-Backport |
| 5.15 LTS | CVE-2022-42896, CVE-2024-36013 | prüfe den Stable-Backport |
| 6.1 LTS | CVE-2024-41062, CVE-2024-49950 | prüfe den Stable-Backport |
| 6.6 LTS | CVE-2026-98107, CVE-2026-98457 | prüfe den Stable-Backport |
| 6.12+ | meist DoS | prüfe jeden Fix |

## QEMU

Nutze einen Distributions-Kernel, der zur Matrix passt, nicht den Host-Kernel.
Hänge im Gast einen virtuellen Controller über `btvirt` oder `vhci` an. Führe
dieselbe Bench mit `--transport hci-socket:0` aus.

Ein negatives L2CAP-Ergebnis heißt nur, dass der Pfad diesen Build nicht zum
Absturz brachte. Es ist kein Beweis, dass keine Schwachstelle vorliegt.
