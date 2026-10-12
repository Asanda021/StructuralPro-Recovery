"""Priority 22 regression tests."""
from core.performance.project_performance import chunked, paginate, project_performance_snapshot

def test_chunked_and_paginate():
    assert list(chunked(range(5),2)) == [[0,1],[2,3],[4]]
    page=paginate(list(range(5)),page=2,page_size=2)
    assert page["items"]==[2,3] and page["total_pages"]==3 and page["has_next"] is True

def test_large_project_snapshot_is_deterministic():
    project={"id":"P22","takeoffs":[{}]*10000,"boq":[{}]*2}
    s=project_performance_snapshot(project)
    assert s["total_collection_rows"]==10002
    assert s["largest_collection"]=="takeoffs"
    assert s["large_project"] is True
