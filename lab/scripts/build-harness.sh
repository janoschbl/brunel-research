#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
bluez="$root/lab/build/bluez"
out="$root/lab/build/harness"
mkdir -p "$out"

if [ ! -f "$bluez/src/eir.c" ]; then
  echo "bluez 5.78 is not built; run lab/scripts/build-bluez.sh first" >&2
  exit 1
fi

clang -fsanitize=address -fno-omit-frame-pointer -g -O1 \
  -I "$bluez" -I "$bluez/lib" -I "$bluez/src" -I "$bluez/src/shared" \
  $(pkg-config --cflags glib-2.0) \
  "$root/lab/harness/eir_harness.c" \
  "$bluez/src/eir.c" "$bluez/src/uuid-helper.c" "$bluez/src/shared/util.c" \
  "$bluez/lib/.libs/libbluetooth-internal.a" "$bluez/src/.libs/libshared-glib.a" \
  $(pkg-config --libs glib-2.0) -o "$out/eir_harness"

echo "$out/eir_harness"
