#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
bluez="$root/lab/build/bluez"
out="$root/lab/build/harness"
mkdir -p "$out"

clang -fsanitize=address -fno-omit-frame-pointer -g -O1 \
  -I "$bluez" -I "$bluez/lib" -I "$bluez/src" -I "$bluez/src/shared" \
  $(pkg-config --cflags glib-2.0) \
  "$root/lab/harness/gatt_db_harness.c" \
  "$bluez/src/shared/gatt-db.c" "$bluez/src/shared/queue.c" \
  "$bluez/src/shared/util.c" "$bluez/src/uuid-helper.c" \
  "$bluez/lib/.libs/libbluetooth-internal.a" "$bluez/src/.libs/libshared-glib.a" \
  $(pkg-config --libs glib-2.0) -o "$out/gatt_db_harness"

echo "$out/gatt_db_harness"
