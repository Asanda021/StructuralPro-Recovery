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
    result=app.add_assembly_takeoff("P1","excavation",args,floor_id="L1",
                                    measurement_source="excavation:L1:zoneA",
                                    approved_by="reviewer")
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



@pytest.mark.parametrize("domain,item,params", [
    ("building","column",{"width":.4,"depth":.5,"height":3}),
    ("advanced","footing_concrete",{"length":2,"width":2,"thickness":.5}),
    ("mechanical","pipe",{"length":8}),
    ("electrical","cable",{"length":9}),
    ("building","tile",{"length":5,"height":2}),
    ("building","roof_insulation",{"length":5,"width":3}),
])
def test_legacy_takeoff_never_guesses_member_count_waste_or_layers(tmp_path,domain,item,params):
    app=_app(tmp_path)
    with pytest.raises(ValueError,match="پیش‌فرض"):
        app.add_takeoff("P1",domain,item,source_id="source:one",**params)
    assert app.open_project("P1")["takeoffs"] == []
    app.store.close()



def test_priced_boq_without_approved_pricebook_cannot_enter_estimate(tmp_path):
    app=_app(tmp_path)
    app.add_takeoff("P1", "building", "column", source_id="manual:priced:C1",
                    width=.4, depth=.5, height=3, count=1,
                    price_code="USER-CONC", unit_price=250)
    project=app.open_project("P1")
    assert project["boq"][0]["unit_price"] == 250
    original_version=project["_meta"]["version"]
    with pytest.raises(ValueError, match="فهرست‌بها"):
        app.recalculate_estimate("P1")
    assert app.open_project("P1")["_meta"]["version"] == original_version
    app.store.close()


def test_estimate_requires_file_hash_and_approved_pricebook_row_equality(tmp_path):
    import hashlib

    app=_app(tmp_path)
    app.add_takeoff("P1", "building", "column", source_id="manual:priced:C2",
                    width=.4, depth=.5, height=3, count=1,
                    price_code="USER-CONC", unit_price=250)
    catalog=tmp_path / "reviewed-pricebook.csv"
    catalog.write_text("USER-CONC,concrete,m3,250", encoding="utf-8")
    document=app.open_project("P1")
    document["user_pricebook_review"]={
        "status":"approved", "approved_by":"کارشناس دفتر فنی",
        "path":str(catalog), "sha256":hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "rows_by_code":{"USER-CONC":{"unit":"m3", "unit_price":250}},
    }
    app.store.save("P1", document, expected_digest=app.store.current_digest("P1"))
    actual=app.recalculate_estimate("P1")
    assert actual["cost"]["grand_total"] > 0
    catalog.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="تغییر"):
        app.recalculate_estimate("P1")
    app.store.close()


def test_estimate_requires_pricebook_same_units_and_rates(tmp_path):
    import hashlib

    app=_app(tmp_path)
    app.add_takeoff("P1", "building", "column", source_id="manual:priced:C3",
                    width=.4, depth=.5, height=3, count=1,
                    price_code="USER-CONC", unit_price=250)
    catalog=tmp_path / "pricebook.csv"
    catalog.write_text("user catalog", encoding="utf-8")
    project=app.open_project("P1")
    project["user_pricebook_review"]={
        "status":"approved", "approved_by":"کارشناس",
        "path":str(catalog), "sha256":hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "rows_by_code":{"USER-CONC":{"unit":"kg", "unit_price":250}},
    }
    app.store.save("P1", project, expected_digest=app.store.current_digest("P1"))
    with pytest.raises(ValueError, match="واحد"):
        app.recalculate_estimate("P1")
    project=app.open_project("P1")
    project["user_pricebook_review"]["rows_by_code"]["USER-CONC"]={"unit":"m3","unit_price":200}
    app.store.save("P1", project, expected_digest=app.store.current_digest("P1"))
    with pytest.raises(ValueError, match="قیمت"):
        app.recalculate_estimate("P1")
    app.store.close()
