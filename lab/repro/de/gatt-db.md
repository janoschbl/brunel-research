# GATT-Datenbank-Harness

[English](../en/gatt-db.md) · [Deutsch](gatt-db.md)

`gatt_db_harness.c` baut eine kleine Datenbank und ruft die Bereichssuchen mit
Grenzwerten auf:

- `0x0001..0xffff`
- `0xffff..0xffff`
- `0x0000..0x0000`
- umgekehrte Bereiche
- Bereiche mit einem einzigen Handle

Das Programm läuft unter ASan. Es ist ein Smoke-Test, kein CVE-Reproducer. Die
Feldproben `att_find_by_type`, `att_read_by_type` und `att_read_by_group` nutzen
dieselben Pfade über Funk.

```sh
lab/scripts/build-gatt-harness.sh
lab/build/harness/gatt_db_harness
```

Ein Absturz hier ist ein Parser- oder Bereichsfehler in `src/shared/gatt-db.c`.
Ein sauberer Lauf heißt nur, dass diese Bereiche sicher sind.
