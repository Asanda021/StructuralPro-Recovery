"""Deterministic in-memory sync provider used for offline/E2E tests and demos."""
from __future__ import annotations
from copy import deepcopy


class MemorySyncProvider:
    def __init__(self):
        self.records = {}

    def push(self, records):
        acknowledged_ids = []
        for r in records:
            self.records[(str(r["project_id"]), int(r["version"]))] = deepcopy(r)
            record_id = r.get("record_id")
            if record_id is not None:
                acknowledged_ids.append(str(record_id))
        result = {"pushed": len(records)}
        if acknowledged_ids:
            result["acknowledged_ids"] = acknowledged_ids
        return result

    def pull(self, project_id):
        rows = [
            deepcopy(v)
            for (pid, _), v in self.records.items()
            if pid == str(project_id)
        ]
        rows.sort(key=lambda x: int(x["version"]))
        return rows
