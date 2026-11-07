#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
python="$root/.venv/bin/python"

if [ ! -x "$python" ]; then
  echo "create the venv first: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

sudo setcap cap_net_raw,cap_net_admin+ep "$(readlink -f "$python")"

rule=/etc/udev/rules.d/99-brunel-ble.rules
sudo tee "$rule" >/dev/null <<'EOF'
# allow the active user to open bluetooth usb adapters
SUBSYSTEM=="usb", ATTR{bDeviceClass}=="e0", MODE="0660", GROUP="uucp"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb

echo "done. replug the adapter, then run:"
echo "  .venv/bin/brunel scan --transport hci-socket:0"
echo "or:"
echo "  .venv/bin/brunel scan --transport usb:0"
