#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
"$root/lab/scripts/repro-eir.sh"
"$root/lab/scripts/build-gatt-harness.sh" >/dev/null
"$root/lab/build/harness/gatt_db_harness"
echo "all harnesses done"
