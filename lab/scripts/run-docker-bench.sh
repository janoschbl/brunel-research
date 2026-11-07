#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
level="${1:-dos}"

cd "$root/lab"
docker compose up -d --build
trap 'docker compose down' EXIT

for _ in $(seq 1 30); do
  if (echo >/dev/tcp/127.0.0.1/9000) 2>/dev/null; then break; fi
  sleep 1
done

cd "$root/research"
.venv/bin/brunel bench --transport tcp-client:127.0.0.1:9000 --level "$level" --scan-seconds 20
