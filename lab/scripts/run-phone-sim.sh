#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
transport="${1:-usb:0}"

if [ ! -x "$root/research/.venv/bin/python" ]; then
  echo "create research/.venv first" >&2
  exit 1
fi

cleanup() {
  sudo systemctl start bluetooth 2>/dev/null || true
}
trap cleanup EXIT

sudo systemctl stop bluetooth 2>/dev/null || true
sudo pkill -x bluetoothd 2>/dev/null || true
sleep 1

"$root/research/.venv/bin/python" "$root/lab/phone_sim.py" --transport "$transport" --crash-on-action
