#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
build="$root/lab/build"
bluez="$build/bluez"
prefix="$build/prefix"

mkdir -p "$build"
if [ ! -d "$bluez" ]; then
  git clone --depth 1 --branch 5.78 https://github.com/bluez/bluez.git "$bluez"
fi

cd "$bluez"
# some kernels only register ecb(aes-lib), fall back to that name
if git apply --check "$root/lab/patches/crypto-alg-names.patch" 2>/dev/null; then
  git apply "$root/lab/patches/crypto-alg-names.patch"
fi
[ -x ./configure ] || ./bootstrap
CC=clang CFLAGS="-fsanitize=address -fno-omit-frame-pointer -g -O1" \
  LDFLAGS="-fsanitize=address" \
  ./configure --prefix="$prefix" --disable-systemd --disable-udev \
  --disable-manpages --disable-cups --disable-obex --disable-mesh \
  --disable-monitor --enable-debug --enable-testing
make -j"$(nproc)"
make -j"$(nproc)" emulator/btvirt
"$root/lab/scripts/build-harness.sh"
echo "built $bluez"
