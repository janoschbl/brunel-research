# GATT database harness

[English](gatt-db.md) · [Deutsch](../de/gatt-db.md)

`gatt_db_harness.c` builds a small database and calls the range lookups with
boundary values:

- `0x0001..0xffff`
- `0xffff..0xffff`
- `0x0000..0x0000`
- reversed ranges
- single-handle ranges

It runs under ASan. It is a smoke test, not a CVE reproducer. The field probes
`att_find_by_type`, `att_read_by_type`, and `att_read_by_group` exercise the same
paths over the air.

```sh
lab/scripts/build-gatt-harness.sh
lab/build/harness/gatt_db_harness
```

A crash here is a parser or range bug in `src/shared/gatt-db.c`. A clean run only
means these ranges are safe.
