"""Preserve the validated public OpenF1 queries as attributed offline snapshots."""
import hashlib
import json
import shutil

from f1_analyser.open_data import BUNDLED, CACHE


BUNDLED.mkdir(parents=True, exist_ok=True)
entries = []
for path in sorted(CACHE.glob("*.json")):
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or "endpoint" not in payload:
        continue
    # Do not bundle exploratory invalid time-filter queries.
    if "date>=" in payload["params"] or "date<=" in payload["params"]:
        continue
    shutil.copyfile(path, BUNDLED / path.name)
    entries.append(dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        source=payload["source"], retrieved_utc=payload["retrieved_utc"],
                        endpoint=payload["endpoint"], records=len(payload["data"])))
(BUNDLED / "manifest.json").write_text(json.dumps(dict(
    attribution="OpenF1 contributors, https://openf1.org/", licence="CC BY-NC-SA 4.0",
    licence_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
    purpose="Noncommercial educational lap analysis; selected API responses are unchanged.",
    files=entries), indent=2) + "\n")
print(f"Bundled {len(entries)} public responses.")
