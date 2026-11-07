#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
bluez="$root/lab/build/bluez"
log="$root/lab/logs/self-eir.log"
payload="fb09$(printf 'ff%.0s' $(seq 1 250))"
mkdir -p "$root/lab/logs"

if [ ! -x "$bluez/src/bluetoothd" ]; then
  echo "run lab/scripts/build-bluez.sh first" >&2
  exit 1
fi

cleanup() {
  kill "${adv:-0}" 2>/dev/null || true
  sudo pkill -x bluetoothd 2>/dev/null || true
  sudo systemctl unmask --runtime bluetooth 2>/dev/null || true
  sudo systemctl start bluetooth 2>/dev/null || true
}
trap cleanup EXIT

sudo systemctl stop bluetooth 2>/dev/null || true
sudo systemctl mask --runtime bluetooth 2>/dev/null || true
sudo pkill -x bluetoothd 2>/dev/null || true
sleep 1

# some adapters unbind btusb when the daemon stops, bind them back
for d in /sys/bus/usb/devices/*; do
  [ -f "$d/bDeviceClass" ] || continue
  [ "$(cat "$d/bDeviceClass")" = "e0" ] || continue
  drv="$(basename "$(readlink "$d/driver" 2>/dev/null)" 2>/dev/null || true)"
  [ "$drv" = "btusb" ] && continue
  echo "rebinding $(basename "$d") to btusb"
  echo -n "$(basename "$d")" | sudo tee /sys/bus/usb/drivers/btusb/bind >/dev/null || true
done

for _ in $(seq 1 20); do
  [ -d /sys/class/bluetooth/hci0 ] && break
  sleep 0.5
done
if [ ! -d /sys/class/bluetooth/hci0 ]; then
  echo "no hci0 after rebind; replug the adapter and retry" >&2
  exit 1
fi

sudo env ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
  "$bluez/src/bluetoothd" -n -d -E >"$log" 2>&1 &
sleep 2

if ! pgrep -x bluetoothd >/dev/null; then
  echo "bluetoothd exited at startup:" >&2
  tail -30 "$log" >&2
  exit 1
fi

sudo btmgmt power on >/dev/null 2>&1 || true
sudo btmgmt le on >/dev/null 2>&1 || true
sudo btmgmt advertising on >/dev/null 2>&1 || true
sudo bluetoothctl --timeout 30 scan on >/dev/null 2>&1 &
sleep 3

echo "advertising 252 bytes over raw HCI"
"$root/research/.venv/bin/python" "$root/lab/hci_adv.py" --name-len 250 --seconds 15 >"$root/lab/logs/hci-adv.log" 2>&1 &
adv=$!
sleep 1
if ! grep -q "advertising" "$root/lab/logs/hci-adv.log"; then
  echo "raw HCI advertising failed:" >&2
  cat "$root/lab/logs/hci-adv.log" >&2
  exit 1
fi

for _ in $(seq 1 20); do
  if grep -q "AddressSanitizer" "$log"; then
    echo "PASS: bluetoothd crashed"
    grep -m1 -A6 "AddressSanitizer" "$log"
    exit 0
  fi
  sleep 0.5
done

echo "no ASan crash in 10 s"
echo "note: most controllers do not report their own advertisements, so a single-adapter self-test may never reach bluetoothd."
echo "use the phone as advertiser with run-eir-target.sh, or a second adapter."
tail -30 "$log"
exit 1
