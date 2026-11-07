#!/usr/bin/env bash
set -euo pipefail

sudo btmgmt power on >/dev/null 2>&1 || true
sudo btmgmt le on >/dev/null 2>&1 || true

for n in 0 20 30 31 100 200 248 249 250 251 252 253 254 255; do
  payload="$(printf '%02x' $((n + 1)))09$(printf 'ff%.0s' $(seq 1 "$n"))"
  if sudo btmgmt --timeout 2 add-adv -d "$payload" 42 >/dev/null 2>&1; then
    echo "$((n + 2)) bytes total: ok"
    sudo btmgmt --timeout 2 rm-adv 42 >/dev/null 2>&1 || true
  else
    echo "$((n + 2)) bytes total: rejected"
  fi
done
