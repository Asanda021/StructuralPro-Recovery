from pathlib import Path
import pytest
from core.projects.store import ProjectStore


def test_project_store_rejects_stale_write(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("p1", {"id": "p1", "name": "Demo", "value": 1})
    token = store.begin_write("p1")
    project = store.get("p1")
    project["value"] = 2
    store.save("p1", project, expected_digest=token)
    stale = store.get("p1")
    stale["value"] = 3
    with pytest.raises(RuntimeError, match="changed since write began"):
        store.save("p1", stale, expected_digest=token)
    assert store.get("p1")["value"] == 2
    store.close()


def test_begin_write_is_based_on_persisted_payload(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("p1", {"id": "p1", "name": "Demo", "value": 1})
    token = store.begin_write("p1")
    loaded = store.get("p1")
    loaded["value"] = 9
    # The read-only metadata exposed by get() must not invalidate the token.
    store.save("p1", loaded, expected_digest=token)
    assert store.get("p1")["value"] == 9
    store.close()


def test_write_token_requires_existing_project(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects.db")
    with pytest.raises(KeyError):
        store.begin_write("missing")
    store.close()
