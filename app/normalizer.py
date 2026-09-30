
import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATE_RE = re.compile(r"^/Date\((-?\d+)([+-]\d{4})?\)/$")

def unwrap(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        if isinstance(payload.get("value"), list):
            return payload["value"]
        d = payload.get("d")
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return d["results"]
        if isinstance(d, list):
            return d
    if isinstance(payload, list):
        return payload
    return []

def parse_sap_date(value):
    if not isinstance(value, str):
        return value
    m = DATE_RE.match(value)
    if not m:
        return value
    ms = int(m.group(1))
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

def normalize(value):
    if isinstance(value, dict):
        # Ignore OData metadata/deferred navigation for this deterministic POC.
        if "__metadata" in value and len(value) == 1:
            return None
        if "__deferred" in value:
            return None
        return {k: normalize(v) for k, v in value.items() if k != "__metadata"}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return parse_sap_date(value)

def load_json(path):
    return normalize(json.loads(Path(path).read_text(encoding="utf-8")))

def first_record(path):
    rows = unwrap(load_json(path))
    return rows[0] if rows else None

def safe_key(label, key):
    return f"{label}:{key}"
