#!/usr/bin/env bash
# build the bus module emulator and its symbol table
#
# profiles:
#   plain   no canary, non-PIE, fixed addresses
#   canary  stack canary, non-PIE, fixed addresses
#   pie     64 relocated PIE builds, stack canary, base is the variable
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
out="$root/lab/build/emulator"
src="$root/lab/emulator/bus_module.c"
tc="${ARM_TC:-/mnt/storage/offload/toolchains/arm-linux-musleabihf-cross/bin}"
cc="$tc/arm-linux-musleabihf-gcc"
nm="$tc/arm-linux-musleabihf-nm"
readelf="$tc/arm-linux-musleabihf-readelf"

flags=(-static -O0 -g -mthumb -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard
       -fomit-frame-pointer -fno-asynchronous-unwind-tables)

mkdir -p "$out"

build() {
	local name="$1"; shift
	"$cc" "${flags[@]}" "$@" -o "$out/$name" "$src"
}

symbols() {
	local name="$1" base="${2:-0}" offset="$3" canary="$4"
	local gadget lgadget system shadow cont setcb backdoor

	gadget=$((0x$("$nm" -n "$out/$name" | awk '$3=="pop_r0_r4_pc"{print $1}') - base))
	lgadget=$((0x$("$nm" -n "$out/$name" | awk '$3=="pop_r0_lr_pc"{print $1}') - base))
	system=$((0x$("$nm" -n "$out/$name" | awk '$3=="system"{print $1}') - base))
	shadow=$((0x$("$nm" -n "$out/$name" | awk '$3=="action_shadow"{print $1}') - base))
	cont=$((0x$("$nm" -n "$out/$name" | awk '$3=="emu_continue"{print $1}') - base))
	setcb=$((0x$("$nm" -n "$out/$name" | awk '$3=="set_action_cb"{print $1}') - base))
	backdoor=$((0x$("$nm" -n "$out/$name" | awk '$3=="backdoor"{print $1}') - base))
	printf '{"name":"%s","base":%d,"gadget":%d,"gadget_lr":%d,"system":%d,"command":%d,"continue":%d,"set_cb":%d,"backdoor":%d,"offset":%d,"canary_offset":%s}\n' \
		"$name" "$base" "$gadget" "$lgadget" "$system" "$shadow" "$cont" "$setcb" "$backdoor" "$offset" "$canary"
}

build plain -fno-stack-protector -fno-pic -no-pie
build canary -fstack-protector-strong -fno-pic -no-pie

for i in $(seq 0 63); do
	base=$(printf '0x%x' $((0x400000 + i * 0x1000)))
	build "pie_$i" -fstack-protector-strong -fPIE -pie "-Wl,-Ttext-segment=$base"
done

{
	symbols plain 0 260 null
	symbols canary 0 264 256
	for i in $(seq 0 63); do
		actual=$(($("$readelf" -l "$out/pie_$i" | awk '/LOAD/{print $3; exit}')))
		symbols "pie_$i" "$actual" 264 256
	done
} > "$out/symbols.jsonl"

echo "built $out"
