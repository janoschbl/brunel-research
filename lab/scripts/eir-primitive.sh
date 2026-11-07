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

common=(
  -g -O1 -fno-omit-frame-pointer
  -I "$bluez" -I "$bluez/lib" -I "$bluez/src" -I "$bluez/src/shared"
)
asan_libs=(
  "$bluez/src/eir.c" "$bluez/src/uuid-helper.c" "$bluez/src/shared/util.c"
  "$bluez/lib/.libs/libbluetooth-internal.a" "$bluez/src/.libs/libshared-glib.a"
)

clang "${common[@]}" $(pkg-config --cflags glib-2.0) \
  "$root/lab/harness/eir_primitive.c" \
  "$bluez/src/eir.c" "$bluez/src/uuid-helper.c" "$bluez/src/shared/util.c" \
  $(pkg-config --libs glib-2.0) -lbluetooth -o "$out/eir_primitive"

clang -fsanitize=address "${common[@]}" $(pkg-config --cflags glib-2.0) \
  "$root/lab/harness/eir_primitive.c" "${asan_libs[@]}" \
  $(pkg-config --libs glib-2.0) -o "$out/eir_primitive-asan"

echo "plain: $out/eir_primitive"
echo "asan:  $out/eir_primitive-asan"
echo
echo "== plain, 253-byte name, marker 0x41"
"$out/eir_primitive" 253 0x41 || true
echo
echo "== ASan, same input"
set +e
ASAN_OPTIONS=detect_leaks=0 "$out/eir_primitive-asan" 253 0x41 2>&1 | grep -m1 -A3 "AddressSanitizer" || true
