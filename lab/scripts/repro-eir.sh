#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
bluez="$root/lab/build/bluez"
harness="$root/lab/build/harness/eir_harness"
source_file="$bluez/src/eir.c"

[ -x "$harness" ] || "$root/lab/scripts/build-harness.sh" >/dev/null

echo "== vulnerable 5.78"
set +e
"$harness" 253 >"$root/lab/build/eir-vulnerable.txt" 2>&1
vuln=$?
set -e
grep -m1 "ERROR: AddressSanitizer" "$root/lab/build/eir-vulnerable.txt" || true
echo "exit=$vuln"

echo "== patched"
cp "$source_file" "$source_file.orig"
python3 - "$source_file" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
old = "\tchar utf8_name[HCI_MAX_NAME_LENGTH + 2];\n\tint i;\n"
new = "\tchar utf8_name[HCI_MAX_NAME_LENGTH + 2];\n\tint i;\n\n\tif (len > HCI_MAX_NAME_LENGTH)\n\t\tlen = HCI_MAX_NAME_LENGTH;\n"
if old not in text:
    raise SystemExit("clamp site not found")
path.write_text(text.replace(old, new, 1))
PY
"$root/lab/scripts/build-harness.sh" >/dev/null
set +e
"$harness" 253 >"$root/lab/build/eir-patched.txt" 2>&1
fixed=$?
set -e
mv "$source_file.orig" "$source_file"
"$root/lab/scripts/build-harness.sh" >/dev/null
cat "$root/lab/build/eir-patched.txt"
echo "exit=$fixed"

if [ "$vuln" -ne 0 ] && [ "$fixed" -eq 0 ]; then
  echo "PASS: overflow reproduced and the clamp fixes it"
else
  echo "FAIL: vulnerable=$vuln patched=$fixed"
  exit 1
fi
