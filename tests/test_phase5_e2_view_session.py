"""E2 session snapshot: identity, hash, CAS, crash and isolation."""
import json
import pytest
from core.platform.autosave import write_view_session, read_view_session

VIEW={"document_id":"D1","floor_id":"F2","member_id":"C4","zoom_2d":1.75,"current_tab":"boq"}
HASHES={"D1":"a"*64}


def _write(tmp_path, **kw):
    target=tmp_path/"session.json"
    write_view_session(target,project_id="P1",revision=8,subject_id="uid:1000",
                       view=VIEW,document_hashes=HASHES,**kw)
    return target


def _read(target, **kw):
    return read_view_session(target,project_id="P1",revision=8,subject_id="uid:1000",
                             document_hashes=HASHES,existing_ids={"member_id":{"C4"},"floor_id":{"F2"}},**kw)


def test_e2_roundtrip_is_view_only_and_deepcopy(tmp_path):
    target=_write(tmp_path)
    restored=_read(target)
    assert restored==VIEW
    restored["zoom_2d"]=500
    assert _read(target)==VIEW
    raw=json.loads(target.read_text())
    assert raw["payload"]["view"]==VIEW
    assert "boq" not in raw["payload"] and "financial_documents" not in raw["payload"]


def test_e2_fail_closed_revision_actor_project_document_and_selection(tmp_path):
    target=_write(tmp_path)
    with pytest.raises(ValueError,match="revision conflict"):
        read_view_session(target,project_id="P1",revision=9,subject_id="uid:1000",document_hashes=HASHES)
    with pytest.raises(PermissionError,match="identity mismatch"):
        read_view_session(target,project_id="P1",revision=8,subject_id="uid:2000",document_hashes=HASHES)
    with pytest.raises(ValueError,match="project_id mismatch"):
        read_view_session(target,project_id="P2",revision=8,subject_id="uid:1000",document_hashes=HASHES)
    with pytest.raises(ValueError,match="digest conflict"):
        read_view_session(target,project_id="P1",revision=8,subject_id="uid:1000",document_hashes={"D1":"b"*64})
    with pytest.raises(ValueError,match="stale session selection"):
        read_view_session(target,project_id="P1",revision=8,subject_id="uid:1000",
                          document_hashes=HASHES,existing_ids={"member_id":{"C5"}})


def test_e2_rejects_corruption_symlink_and_unverified_fields(tmp_path):
    target=_write(tmp_path)
    snapshot=json.loads(target.read_text())
    snapshot["payload"]["view"]["floor_id"]="forged"
    target.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError,match="integrity"):
        _read(target)
    link=tmp_path/"link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError,match="unsafe"):
        _read(link)
    with pytest.raises(ValueError,match="unsupported"):
        write_view_session(tmp_path/"bad.json",project_id="P1",revision=1,subject_id="uid:1000",
                           view={"approved_estimate":123},document_hashes={})


def test_e2_atomic_no_replace_and_crash_cleanup(tmp_path,monkeypatch):
    target=_write(tmp_path)
    before=target.read_bytes()
    with pytest.raises(FileExistsError):
        _write(tmp_path)
    assert target.read_bytes()==before
    target.unlink()
    from core.platform import autosave
    def fail_link(*args,**kwargs):
        raise OSError("simulated crash before publication")
    monkeypatch.setattr(autosave.os,"link",fail_link)
    with pytest.raises(OSError,match="simulated crash"):
        _write(tmp_path)
    assert not target.exists() and not list(tmp_path.glob(".session-*"))
