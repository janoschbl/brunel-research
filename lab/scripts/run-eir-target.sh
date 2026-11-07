#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
bluez="$root/lab/build/bluez"
log="$root/lab/logs/eir-target.log"
mkdir -p "$root/lab/logs"

if [ ! -x "$bluez/src/bluetoothd" ]; then
  echo "run lab/scripts/build-bluez.sh first" >&2
  exit 1
fi

cleanup() {
  sudo pkill -x bluetoothd 2>/dev/null || true
  sudo systemctl start bluetooth 2>/dev/null || true
}
trap cleanup EXIT

sudo systemctl stop bluetooth 2>/dev/null || true
sudo pkill -x bluetoothd 2>/dev/null || true
sleep 1

sudo env ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
  "$bluez/src/bluetoothd" -n -d -E >"$log" 2>&1 &
sleep 2

sudo btmgmt power on >/dev/null 2>&1 || true
echo "5.78 target up on hci0. Start the phone EIR probe now. Ctrl-C to stop."
echo "log: $log"
sudo btmgmt find
