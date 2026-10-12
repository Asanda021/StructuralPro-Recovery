"""Durable local queue for offline edits."""
from __future__ import annotations
import json
from pathlib import Path
class OfflineQueue:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def _read(self):
        if not self.path.exists(): return []
        return json.loads(self.path.read_text(encoding="utf-8"))
    def enqueue(self,record):
        rows=self._read(); rows.append(record); self.path.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    def peek(self): return self._read()
    def clear(self): self.path.write_text("[]",encoding="utf-8")
    def __len__(self): return len(self._read())
