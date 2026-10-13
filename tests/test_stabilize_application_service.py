"""Production application-level integration guards for P10–P12.

Requires full StructuralProApp dependencies. No GUI, Workflows or packaged build.
"""
from __future__ import annotations

import pytest
from core.platform.application import StructuralProApp


def _app(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("پروژه نمونه", "P1")
    return app


def test_manual_source_id_mandatory_and_duplicate_is_fail_closed(tmp_path):
    app=_app(tmp_path)
    with pytest.raises(ValueError):
        app.add_takeoff("P1","building","column",width=.4,depth=.5,height=3,count=1)
    first=app.add_takeoff("P1","building","column",source_id="manual:L1:C1",
                          width=.4,depth=.5,height=3,count=1)
    assert first["quantities"][0]["amount"] == pytest.approx(.6)
    with pytest.raises(ValueError,match="تکرار|قبلاً"):
        app.add_takeoff("P1","building","column",source_id="manual:L1:C1",
                        width=.4,depth=.5,height=3,count=1)
    assert len(app.open_project("P1")["takeoffs"]) == 1
    app.store.close()


def test_direct_manual_takeoff_reconciles_with_boq(tmp_path):
    app=_app(tmp_path)
    row=app.add_takeoff("P1","building","column",source_id="manual:C1",
                        width=.4,depth=.5,height=3,count=1)
    p=app.open_project("P1")
    assert p["takeoffs"][0]["source_id"] == row["source_id"]
    assert p["boq"][0]["quantity"] == pytest.approx(.6)
    assert p["boq"][0]["unit_price"] is None
    app.store.close()


def test_manual_source_cannot_reuse_structural_draft_identity(tmp_path):
    app=_app(tmp_path)
    draft=app.new_structural_member("column","L1","C1")
    draft["source"]={"mode":"manual","source_id":"unique:C1"}
    app.save_structural_member_draft("P1",draft)
    with pytest.raises(ValueError):
        app.add_takeoff("P1","building","column",source_id="unique:C1",
                        width=.4,depth=.5,height=3,count=1)
    assert not app.open_project("P1")["takeoffs"]
    app.store.close()


def test_empty_assembly_details_never_modify_project(tmp_path):
    app=_app(tmp_path)
    before=app.open_project("P1")["_meta"]["version"]
    with pytest.raises(ValueError):
        app.add_assembly_takeoff("P1","block_wall",{},floor_id="L1")
    project=app.open_project("P1")
    assert project["_meta"]["version"] == before
    assert project["takeoffs"] == [] and project["boq"] == []
    app.store.close()


def test_reviewed_assembly_parts_commit_in_one_sqlite_revision(tmp_path):
    app=_app(tmp_path)
    args={"count":1,"length":6,"width":4,"depth":.5}
    before=app.open_project("P1")["_meta"]["version"]
    result=app.add_assembly_takeoff("P1","excavation",args,floor_id="L1")
    after=app.open_project("P1")
    assert after["_meta"]["version"]==before+1
    assert len(result["rows"])==1
    assert len(after["takeoffs"])==1 and len(after["boq"])==1
    app.store.close()


def test_financial_report_cannot_treat_unpriced_work_as_zero(tmp_path):
    app=_app(tmp_path)
    app.add_takeoff("P1","building","column",source_id="manual:C1",
                    width=.4,depth=.5,height=3,count=1)
    before=app.open_project("P1")["_meta"]["version"]
    with pytest.raises(ValueError,match="قیمت|فهرست‌بها"):
        app.recalculate_estimate("P1")
    assert app.open_project("P1")["_meta"]["version"]==before
    app.store.close()


def test_manual_revision_uses_shared_boq_builder_and_retains_provenance(tmp_path):
    app=_app(tmp_path)
    app.add_takeoff("P1","building","column",source_id="manual:C1",
                    width=.4,depth=.5,height=3,count=1)
    after=app.revise_takeoff("P1","manual:C1",expected_revision=1,
                             domain="building",item="column",
                             width=.5,depth=.5,height=3,count=1)
    assert after["revision"] == 2
    assert app.open_project("P1")["boq"][0]["quantity"] == pytest.approx(.75)
    assert len(app.open_project("P1")["takeoff_revision_history"]) == 1
    app.store.close()


def test_drawn_or_reviewed_item_cannot_be_revised_via_generic_manual_editor(tmp_path):
    app=_app(tmp_path)
    row=app.add_takeoff("P1","building","column",source_id="manual:C1",
                        width=.4,depth=.5,height=3,count=1)
    pid="P1"
    project=app.open_project(pid)
    project["takeoffs"][0]["review"]={"approved_by":"checker"}
    app.store.save(pid,project,expected_digest=app.store.begin_write(pid))
    before=app.open_project(pid)["_meta"]["version"]
    with pytest.raises(ValueError,match="بازبینی تخصصی"):
        app.revise_takeoff(pid,"manual:C1",expected_revision=1,
                           domain="building",item="column",
                           width=.5,depth=.5,height=3,count=1)
    assert app.open_project(pid)["_meta"]["version"]==before
    app.store.close()
