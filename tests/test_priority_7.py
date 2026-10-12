from core.projects.integrity import ProjectIntegrity, validate_project, missing_data
from core.projects.audit import AuditTrail
from core.projects.import_export import export_project, import_project, fingerprint, round_trip
from core.projects.backup import BackupManager
from core.history.project_commands import ProjectHistory
from core.revisions.manager import RevisionManager
import json, zipfile

def valid_project():
    return {"id":"P1","name":"Test","client":"C","contractor":"K","contract_number":"CN1",
            "drawings":[{"id":"D1","path":"a.pdf"}],"takeoffs":[{"id":"T1","quantity":10}],
            "boq":[{"id":"B1","quantity":10}],"estimates":[{"id":"E1","total":100}]}

def test_qc_valid_and_duplicate_and_invalid_number():
    p=valid_project()
    assert validate_project(p)["valid"]
    p["boq"].append({"id":"B1","quantity":1})
    p["estimates"][0]["total"]=float("nan")
    result=validate_project(p)
    codes={x["code"] for x in result["issues"]}
    assert {"duplicate_id","invalid_number"} <= codes

def test_missing_data_is_explicit_not_overrequired():
    assert missing_data({"id":"P1","name":"X","client":""}) == [{"code":"missing_client","field":"client"}]

def test_audit_lifecycle():
    a=AuditTrail()
    a.record("create","project","P1",after={"name":"X"})
    a.record("update","project","P1",before={"name":"X"},after={"name":"Y"})
    assert [x["action"] for x in a.list()] == ["create","update"]
    try: a.record("wat","project")
    except ValueError: pass
    else: assert False

def test_import_export_round_trip():
    p=valid_project()
    raw=export_project(p)
    assert import_project(raw)==p
    restored, same=round_trip(p)
    assert restored==p and same and fingerprint(p)==fingerprint(restored)

def test_import_rejects_invalid_schema_and_project():
    try: import_project(json.dumps({"schema_version":99,"project":valid_project()}))
    except ValueError: pass
    else: assert False
    bad=valid_project(); bad["boq"][0]["quantity"]=-1
    try: export_project(bad)
    except ValueError: pass
    else: assert False

def test_backup_zip_round_trip_and_corruption(tmp_path):
    bm=BackupManager(tmp_path)
    p=valid_project()
    path=bm.create(p,"P1")
    assert path.exists()
    assert bm.restore(path)==p
    package=bm.create_package(p,"P1")
    assert bm.restore_package(package)==p
    with zipfile.ZipFile(package,"r") as z:
        assert {"manifest.json","project.json"} <= set(z.namelist())
    corrupt=tmp_path/"bad.spbackup"; corrupt.write_bytes(b"not a zip")
    try: bm.restore_package(corrupt)
    except ValueError: pass
    else: assert False

def test_history_atomic_undo_redo():
    p={"id":"P1","name":"A"}
    h=ProjectHistory(p)
    h.set_value(["name"],"B")
    assert p["name"]=="B" and h.undo() and p["name"]=="A" and h.redo() and p["name"]=="B"
    try: h.set_value(["missing","x"],1)
    except (KeyError,ValueError): pass
    else: assert False
    assert p["name"]=="B"

def test_revision_restore():
    r=RevisionManager()
    r.add([{"code":"A","quantity":1,"total":10}],"v1")
    r.add([{"code":"A","quantity":2,"total":20}],"v2")
    assert r.compare(1,2)["summary"]["changed"]==1
    restored=r.restore(1)
    assert restored.rows==[{"code":"A","quantity":1,"total":10}]

# Priority 7 CI diagnostic synchronization marker.

# CI isolation marker.

# workflow isolation marker.

# backup isolation marker.

# Priority 7 final verification marker.
