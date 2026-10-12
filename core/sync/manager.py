"""Offline-first synchronization manager."""
from __future__ import annotations
from core.sync.conflicts import merge_dict
from core.sync.contracts import SyncResult
import json

class SyncManager:
    def __init__(self,provider=None,queue=None):
        self.provider=provider; self.queue=queue
    @property
    def online(self): return self.provider is not None
    def record_local_change(self,record): return self.enqueue(record)
    def enqueue(self,record):
        if self.queue is None: raise RuntimeError("sync queue is not configured")
        return self.queue.enqueue(record)
    def sync(self,project_id=None):
        if self.provider is None:
            return SyncResult(0,0,0,["no_sync_provider"])
        pending=self.queue.peek() if self.queue else []
        if project_id is not None:
            pending=[r for r in pending if str(r.get("project_id"))==str(project_id)]
        pushed=0
        errors=[]
        if pending:
            try:
                result=self.provider.push(pending)
                pushed=int(result.get("pushed",len(pending)))
                acknowledged=result.get("acknowledged_ids")
                if acknowledged is None:
                    acknowledged=[r.get("record_id") for r in pending if r.get("record_id") is not None][:pushed]
                acknowledged={str(x) for x in acknowledged if x is not None}
                all_rows=self.queue.peek() if self.queue else []
                if acknowledged:
                    remaining=[r for r in all_rows if str(r.get("record_id")) not in acknowledged]
                else:
                    # Legacy providers may not return record IDs; remove only the
                    # leading records explicitly counted as pushed.
                    pending_count=min(max(pushed,0),len(pending))
                    remaining=list(all_rows)
                    for target in pending[:pending_count]:
                        for index,row in enumerate(remaining):
                            if row == target:
                                remaining.pop(index)
                                break
                if self.queue:
                    self.queue.path.write_text(json.dumps(remaining,ensure_ascii=False,sort_keys=True),encoding="utf-8")
            except Exception as exc:
                errors.append("push_failed:"+type(exc).__name__)
                pushed=0
        try:
            pulled=len(self.provider.pull(project_id)) if project_id is not None else 0
        except Exception as exc:
            errors.append("pull_failed:"+type(exc).__name__)
            pulled=0
        return SyncResult(pushed,pulled,0,errors)
    @staticmethod
    def merge(base,local,remote): return merge_dict(base,local,remote)
