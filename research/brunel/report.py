# render a bench session as a self-contained html report

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

STYLE = """
:root{--bg:#f6f5fa;--surface:#fff;--fg:#1b1830;--muted:#5d5a73;--line:#d6d2e4;--accent:#1f6feb;--bad:#c0443a;--good:#2f8a4c;--warn:#a86a12;--code:#efedf5}
@media(prefers-color-scheme:dark){:root{--bg:#12101c;--surface:#1b1829;--fg:#e9e6f4;--muted:#a39fbb;--line:#34304a;--accent:#6ea8f0;--bad:#f07a70;--good:#6cc78a;--warn:#e0b060;--code:#221f33}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:32px 18px 80px;display:grid;gap:28px}
h1,h2,h3{margin:0;line-height:1.2}h1{font-size:1.8rem}h2{font-size:1.25rem}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px;display:grid;gap:8px}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:.9rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{background:var(--code);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
tr:last-child td{border-bottom:0}.pill{display:inline-block;font:600 .72rem/1 ui-monospace,monospace;padding:4px 7px;border-radius:999px;background:var(--code)}
.finding{background:var(--good);color:#fff}.crash{background:var(--bad);color:#fff}.error{background:var(--warn);color:#fff}
code,pre{font-family:ui-monospace,monospace;font-size:.82rem;background:var(--code);border-radius:6px}code{padding:1px 5px}pre{padding:12px;overflow:auto}
.muted{color:var(--muted)}
"""


def _e(value: Any) -> str:
    return html.escape(str(value))


def render(session_dir: Path, output: Path) -> Path:
    meta = json.loads((session_dir / "session.json").read_text())
    bench = json.loads((session_dir / "bench.json").read_text()) if (session_dir / "bench.json").exists() else {}
    events = []
    for line in (session_dir / "events.jsonl").read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    findings = [e for e in events if e["type"] in ("finding", "crash_suspected", "crash_recovered", "crash_unrecovered")]
    results = [e for e in events if e["type"] == "probe_result"]
    targets = [e for e in events if e["type"] == "target"]
    rows = []
    for event in results:
        data = event["data"]
        status = data.get("status", "")
        rows.append(
            f"<tr><td>{_e(data.get('probe'))}</td><td><span class='pill {_e(status)}'>{_e(status)}</span></td>"
            f"<td>{_e(data.get('severity'))}</td><td>{_e(data.get('summary'))}</td><td>{_e(data.get('cve') or '')}</td></tr>"
        )
    target_rows = []
    for event in targets:
        data = event["data"]
        target_rows.append(
            f"<tr><td><code>{_e(data.get('address'))}</code></td><td>{_e(data.get('rssi'))}</td>"
            f"<td>{_e(data.get('name'))}</td><td>{_e(', '.join(data.get('fingerprint', {}).get('tags', [])))}</td></tr>"
        )
    finding_rows = []
    for event in findings:
        data = event["data"]
        finding_rows.append(
            f"<tr><td>{_e(event['type'])}</td><td>{_e(data.get('probe') or data.get('address'))}</td>"
            f"<td>{_e(data.get('summary') or data.get('downtime_ms') or data.get('silence_ms'))}</td></tr>"
        )
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Brunel bench {_e(meta.get('sessionId'))}</title>
<style>{STYLE}</style></head><body><main>
<h1>Brunel bench report</h1>
<p class="muted">Session {_e(meta.get('sessionId'))} · level {_e(meta.get('level'))} · started {_e(meta.get('startedUtc'))} · state {_e(meta.get('state'))}</p>
<section class="card"><h2>Summary</h2>
<p>{len(targets)} targets, {len(results)} probe results, {len(findings)} findings/crash events.</p>
<pre>{_e(json.dumps(bench.get('by_status', {}), indent=2))}</pre></section>
<section><h2>Targets</h2><table><tr><th>Address</th><th>RSSI</th><th>Name</th><th>Tags</th></tr>{''.join(target_rows) or '<tr><td colspan=4>none</td></tr>'}</table></section>
<section><h2>Findings and crashes</h2><table><tr><th>Type</th><th>Probe / address</th><th>Detail</th></tr>{''.join(finding_rows) or '<tr><td colspan=3>none</td></tr>'}</table></section>
<section><h2>Probe results</h2><table><tr><th>Probe</th><th>Status</th><th>Severity</th><th>Summary</th><th>CVE</th></tr>{''.join(rows) or '<tr><td colspan=5>none</td></tr>'}</table></section>
<section class="card"><h2>Limits</h2><p>A crash is inferred from advertising silence, not from a device log. A finding is a probe observation, not a confirmed vulnerability. Action writes reach the real vehicle.</p></section>
</main></body></html>"""
    output.write_text(body)
    return output
