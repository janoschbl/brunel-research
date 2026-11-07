#!/usr/bin/env bash
set -euo pipefail

mode="${LAB_MODE:-eir}"
log=/tmp/lab
mkdir -p "$log"

mkdir -p /run/dbus /var/lib/bluetooth
dbus-daemon --system --fork

# one vhci controller for the target and a unix-socket controller for the attacker
/opt/bluez/libexec/bluetooth/btvirt -s -l1 >"$log/btvirt.log" 2>&1 &
sleep 1

socat TCP-LISTEN:9000,fork,reuseaddr UNIX-CONNECT:/tmp/bt-server-le >"$log/socat.log" 2>&1 &

hci="$(ls /sys/class/bluetooth | head -1)"
if [ -n "$hci" ]; then
  bluetoothctl power on >/dev/null 2>&1 || true
  bluetoothctl pairable on >/dev/null 2>&1 || true
fi

if [ "$mode" = "gatt" ]; then
  /opt/bluez/bin/btgatt-server -d >"$log/btgatt-server.log" 2>&1 &
else
  /opt/bluez/libexec/bluetooth/bluetoothd -n -d -E >"$log/bluetoothd.log" 2>&1 &
  sleep 1
  (bluetoothctl --timeout 3600 scan on >"$log/scan.log" 2>&1 &) || true
fi

echo "lab ready: mode=$mode hci=$hci attacker=tcp-client:127.0.0.1:9000"
tail -f "$log/bluetoothd.log" "$log/btgatt-server.log" 2>/dev/null || sleep infinity
