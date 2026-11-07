#!/usr/bin/env bash
# prove the rop builders on x86-64 and armv7
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
out="$root/lab/build/harness"
mkdir -p "$out"
py="$root/research/.venv/bin/python"

cc -O0 -fno-stack-protector -fno-omit-frame-pointer \
  -o "$out/action_rop_x86" "$root/lab/harness/action_rop_x86.c"

if { "$out/action_rop_x86" auto || true; } | grep -q PWNED-X86; then
  echo "PASS x86-64"
else
  echo "FAIL x86-64" >&2
  exit 1
fi

tc=/mnt/storage/offload/toolchains/arm-linux-musleabihf-cross/bin
if [ -x "$tc/arm-linux-musleabihf-gcc" ] && command -v qemu-arm-static >/dev/null; then
  "$tc/arm-linux-musleabihf-gcc" -static -O0 -march=armv7-a -mthumb \
    -mfpu=vfpv3-d16 -mfloat-abi=hard -fno-stack-protector -fomit-frame-pointer \
    -fno-pic -no-pie -o "$out/action_rop_arm" "$root/lab/harness/action_rop_arm.c"
  if { qemu-arm-static "$out/action_rop_arm" auto 2>/dev/null || true; } | grep -q PWNED-ARM; then
    echo "PASS armv7"
  else
    echo "FAIL armv7" >&2
    exit 1
  fi
else
  echo "SKIP armv7: toolchain or qemu missing"
fi
