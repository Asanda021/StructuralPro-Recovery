"""P8 independent architecture audit regressions for project identity collisions.

Runs with disposable SQLite only; no customer input or external services.
"""
from copy import deepcopy

import pytest

from core.platform.application import StructuralProApp
from core.projects.library import ProjectLibrary


def _project_snapshot(app, pid):
    """Read the row, revision history and audit count independently of cache."""
    con = app.store.db
    row = con.execute("SELECT id,name,version,payload FROM projects WHERE id=?", (pid,)).fetchone()
    revs = con.execute("SELECT version,payload FROM revisions WHERE project_id=? ORDER BY version", (pid,)).fetchall()
    acls = con.execute("SELECT subject_id,role,granted_by,source FROM project_acl WHERE project_id=? ORDER BY subject_id", (pid,)).fetchall()
    audits = con.execute("SELECT sequence,event_json,hash FROM security_audit WHERE project_id=? ORDER BY sequence", (pid,)).fetchall()
    return tuple(row), [tuple(r) for r in revs], [tuple(r) for r in acls], [tuple(r) for r in audits]


def test_duplicate_desktop_create_rejected_without_touching_existing_state(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("original", "P")
    project = app.open_project("P")
    project["notes"] = "must survive"
    app.store.save("P", project)
    before = _project_snapshot(app, "P")
    with pytest.raises(ValueError, match="قبلاً"):
        app.create_project("overwrite", "P")
    assert _project_snapshot(app, "P") == before
    assert app.open_project("P")["notes"] == "must survive"
    app.store.close()


def test_duplicate_create_from_distinct_connection_rejected(tmp_path):
    app1 = StructuralProApp(tmp_path / "data")
    app2 = StructuralProApp(tmp_path / "data")
    app1.create_project("original", "P")
    before = _project_snapshot(app1, "P")
    with pytest.raises(ValueError, match="قبلاً"):
        app2.create_project("second creator", "P")
    assert _project_snapshot(app1, "P") == before
    app1.store.close(); app2.store.close()


def test_duplicate_create_rejects_normalized_identity(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("original", "P-1")
    with pytest.raises(ValueError, match="مشابه"):
        app.create_project("collision", "Ｐ-1")
    assert len(app.store.list()) == 1
    app.store.close()


def test_clone_existing_target_rejected_without_data_loss(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("source", "S")
    app.create_project("target", "T")
    p = app.open_project("T")
    p["notes"] = "keep me"
    p["takeoffs"] = [{"id": "measurement", "quantities": []}]
    app.store.save("T", p)
    before = _project_snapshot(app, "T")
    with pytest.raises(ValueError, match="قبلاً"):
        ProjectLibrary(app.store).clone("S", "T")
    assert _project_snapshot(app, "T") == before
    app.store.close()


def test_clone_same_id_or_normalized_collision_rejected(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("source", "S")
    lib = ProjectLibrary(app.store)
    with pytest.raises(ValueError):
        lib.clone("S", "S")
    with pytest.raises(ValueError):
        lib.clone("S", "Ｓ")
    app.store.close()


def test_clone_to_fresh_id_keeps_source_and_creates_new_row(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("source", "S")
    p = app.open_project("S")
    p["takeoffs"] = [{"id": "sample", "quantities": []}]
    app.store.save("S", p)
    before = _project_snapshot(app, "S")
    ProjectLibrary(app.store).clone("S", "T")
    assert _project_snapshot(app, "S") == before
    assert app.open_project("T")["takeoffs"] == p["takeoffs"]
    app.store.close()


def test_clone_without_atomic_create_api_fails_closed(tmp_path):
    class UnsafeStore:
        def __init__(self): self.items={"S":{"id":"S","name":"source"}}
        def get(self,id):return deepcopy(self.items.get(id))
        def list(self):return list(self.items.values())
        def save(self,id,payload):
            self.items[id]=payload
    s=UnsafeStore()
    with pytest.raises(RuntimeError,match="create-only"):
        ProjectLibrary(s).clone("S","T")
    assert "T" not in s.items


def test_atomic_store_prevents_normalized_collision_from_other_connection(tmp_path):
    app1 = StructuralProApp(tmp_path / "data")
    app2 = StructuralProApp(tmp_path / "data")
    app1.create_project("owner", "P9")
    before = _project_snapshot(app1, "P9")
    # Bypasses the UI preflight. The database transaction must still reject it.
    with pytest.raises(ValueError, match="قبلاً"):
        app2.store.save("Ｐ۹", {"id": "Ｐ۹", "name": "alias"}, create_only=True)
    assert _project_snapshot(app1, "P9") == before
    assert app2.store.get("Ｐ۹") is None
    app1.store.close(); app2.store.close()
