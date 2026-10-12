import tempfile
from pathlib import Path
import pytest
from core.sync_engine import SyncEngine,ConflictResolution,SyncRecord
from core.sync_store import JsonSyncStore
from core.platform.clients import ProductClient,ClientRequest,ClientResponse,capability_manifest
from core.platform.telegram import TelegramAdapter

def test_offline_outbox_persists_and_acknowledges():
    e=SyncEngine("android-1"); r=e.apply_local("project","P1",{"name":"Demo"},timestamp="2026-01-01T00:00:00+00:00")
    with tempfile.TemporaryDirectory() as d:
        s=JsonSyncStore(Path(d)/"outbox.json"); s.save(list(e.outbox())); assert s.load()[0].canonical_json()==r.canonical_json()
    e.acknowledge(r.record_id); assert not e.outbox()

def test_conflict_and_explicit_disjoint_merge():
    a,b=SyncEngine("A"),SyncEngine("B")
    a.apply_local("project","P",{"name":"A"},timestamp="2026-01-01T00:00:00+00:00")
    b.apply_local("project","P",{"code":"B"},timestamp="2026-01-01T00:00:00+00:00")
    c=a.receive(b.outbox()[0]); assert c
    assert a.resolve(c,ConflictResolution.MERGE).payload=={"name":"A","code":"B"}

def test_overlapping_fields_cannot_be_silently_merged():
    a,b=SyncEngine("A"),SyncEngine("B")
    a.apply_local("project","P",{"name":"A"},timestamp="2026-01-01T00:00:00+00:00")
    b.apply_local("project","P",{"name":"B"},timestamp="2026-01-01T00:00:00+00:00")
    c=a.receive(b.outbox()[0])
    with pytest.raises(ValueError): a.resolve(c,ConflictResolution.MERGE)

def test_client_contracts():
    assert capability_manifest()["android"]["offline"] and capability_manifest()["windows"]["sync"] and not capability_manifest()["telegram"]["offline"]
    assert ProductClient("android").state()["offline"] is True
    assert ProductClient("windows").state()["offline"] is True
    assert ProductClient("telegram").state()["offline"] is False
    assert ClientRequest("r","android","project.open","P",{}).platform=="android"
    assert ClientResponse("r",True,{}).ok
    with pytest.raises(ValueError): ClientResponse("r",False,{})

def test_telegram_normalization():
    sent=[]; a=TelegramAdapter(lambda chat,text: sent.append((chat,text)) or {"ok":True})
    c=a.parse_update({"update_id":7,"message":{"chat":{"id":123},"text":"/takeoff slab"}})
    assert (c.command,c.text)==("/takeoff","slab"); assert a.send_text(c,"done")["ok"]; assert sent==[("123","done")]

def test_sync_record_validation():
    with pytest.raises(ValueError): SyncRecord("r","project","P","upsert",{},2,2,"d","2026-01-01T00:00:00+00:00")

def test_legacy_product_client_api_remains_available():
    client=ProductClient("windows")
    assert client.open_project("P1")["id"]=="P1"
    assert client.state()["project_id"]=="P1"
