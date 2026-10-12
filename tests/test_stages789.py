from core.reports.project_report import build_report
from core.sync.offline_queue import OfflineQueue
from core.sync.manager import SyncManager

def test_stage7_exports(tmp_path):
    rows=[{"کد":"0101","شرح":"بتن","مقدار":2,"واحد":"m3","مبلغ":100}]
    r=build_report("پروژه آزمایشی",rows,{"grand_total":100})
    assert r.as_rows()==rows
    assert r.export(tmp_path/"x.csv","csv").exists()
    assert r.export(tmp_path/"x.xlsx","xlsx").exists()
    assert r.export(tmp_path/"x.docx","docx").exists()
    assert r.export(tmp_path/"x.pdf","pdf").exists()

def test_stage9_offline_queue(tmp_path):
    q=OfflineQueue(tmp_path/"queue.json"); q.enqueue({"id":"1"}); assert len(q)==1
    assert q.peek()[0]["id"]=="1"; q.clear(); assert len(q)==0

def test_stage9_no_provider_is_offline_safe(tmp_path):
    m=SyncManager(queue=OfflineQueue(tmp_path/"q.json"))
    result=m.sync("P1"); assert result.errors==["no_sync_provider"]
