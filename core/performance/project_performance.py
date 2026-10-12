"""Deterministic performance helpers for large StructuralPro projects."""
from __future__ import annotations
from collections.abc import Iterable, Iterator
from typing import Any
import math

def chunked(items: Iterable[Any], size: int) -> Iterator[list[Any]]:
    size=int(size)
    if size <= 0: raise ValueError("chunk size must be positive")
    batch=[]
    for item in items:
        batch.append(item)
        if len(batch)>=size:
            yield batch; batch=[]
    if batch: yield batch

def paginate(items: Iterable[Any], *, page: int=1, page_size: int=100) -> dict[str,Any]:
    page=int(page); page_size=int(page_size)
    if page < 1 or page_size < 1: raise ValueError("page and page_size must be positive")
    data=items if isinstance(items,list) else list(items)
    total=len(data)
    start=(page-1)*page_size
    return {"items":data[start:start+page_size],"page":page,"page_size":page_size,
            "total":total,"total_pages":math.ceil(total/page_size) if total else 0,
            "has_next":start+page_size<total,"has_previous":page>1 and start<total}

def project_performance_snapshot(project: dict[str,Any]) -> dict[str,Any]:
    p=project if isinstance(project,dict) else {}
    collections=("takeoffs","boq","estimates","reports","drawings","floors",
                  "model_sources","model_objects","project_schedule_tasks",
                  "project_daily_reports","project_resources","project_materials",
                  "project_meetings","financial_documents")
    counts={name:len(p.get(name,[]) or []) for name in collections}
    payload_bytes=len(__import__("json").dumps(p,ensure_ascii=False,separators=(",",":")).encode("utf-8"))
    return {
        "project_id":str(p.get("id","")),
        "payload_bytes":payload_bytes,
        "payload_kib":round(payload_bytes/1024,2),
        "collection_counts":counts,
        "total_collection_rows":sum(counts.values()),
        "largest_collection":max(counts,key=counts.get) if counts else "",
        "largest_collection_count":max(counts.values(),default=0),
        "large_project": sum(counts.values()) >= 10000 or payload_bytes >= 5*1024*1024,
    }
