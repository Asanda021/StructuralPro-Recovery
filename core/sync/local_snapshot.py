"""Portable local sync snapshot for offline backup and later cloud synchronization."""
from __future__ import annotations
import json,hashlib
from pathlib import Path
def export_snapshot(projects,path):
    payload={"schema":1,"projects":list(projects)}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    data={**payload,"sha256":hashlib.sha256(raw.encode()).hexdigest()}
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); return Path(path)
def import_snapshot(path):
    data=json.loads(Path(path).read_text(encoding="utf-8")); supplied=data.pop("sha256",None)
    raw=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    if supplied!=hashlib.sha256(raw.encode()).hexdigest(): raise ValueError("snapshot checksum mismatch")
    return data
