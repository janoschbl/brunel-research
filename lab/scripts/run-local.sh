#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
bluez="$root/lab/build/bluez"
log="$root/lab/build/local"
mode="${1:-eir}"
mkdir -p "$log"

if [ ! -x "$bluez/emulator/btvirt" ]; then
  echo "run lab/scripts/build-bluez.sh first" >&2
  exit 1
fi

cleanup() {
  kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT

sudo -v
sudo "$bluez/emulator/btvirt" -s -l1 >"$log/btvirt.log" 2>&1 &
sleep 1
sudo socat TCP-LISTEN:9000,fork,reuseaddr UNIX-CONNECT:/tmp/bt-server-le >"$log/socat.log" 2>&1 &
sudo "$bluez/src/bluetoothd" -n -d -E >"$log/bluetoothd.log" 2>&1 &
sleep 2
sudo bluetoothctl --timeout 3600 scan on >"$log/scan.log" 2>&1 &

echo "target up, run:"
echo "  research/.venv/bin/brunel bench --transport tcp-client:127.0.0.1:9000 --level ${2:-dos}"
echo "logs: $log"
wait
