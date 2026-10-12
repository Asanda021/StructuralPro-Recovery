"""Deterministic performance smoke benchmarks for large takeoff projects."""
from __future__ import annotations
import time

def benchmark_search(search_fn, project, queries, *, max_seconds=2.0):
    start=time.perf_counter(); total=0
    for q in queries:
        total += len(search_fn(project,q))
    elapsed=time.perf_counter()-start
    return {"queries":len(queries),"hits":total,"seconds":elapsed,"passed":elapsed<=max_seconds}

def synthetic_project(rows=10000):
    return {"name":"Benchmark","takeoffs":[{"title":f"طبقه {i%10}","quantities":[
        {"title":f"دیوار {i}","price_code":f"{i%100:03d}"}]} for i in range(rows)],
        "boq":[{"description":f"آیتم {i}","price_code":f"{i%100:03d}"} for i in range(rows)]}
