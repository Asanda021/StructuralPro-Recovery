"""E6 preview uses the existing Decimal formula engine and canonical CAS."""
import pytest
from decimal import Decimal
from core.platform.application import StructuralProApp
from test_manual_formula_persistence import data


def test_twenty_columns_preview_no_write_then_existing_bulk_apply(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("کنترل ۲۰ ستون","P")
    keys=[]
    for i in range(20):
        key=f"C{i+1}"
        app.save_manual_formula("P",key,data(member=key,source_id="measured:"+key),
                                expected_revision=0,reason="ورودی مستند آزمایشی")
        keys.append(key)
    expected={key:1 for key in keys}
    before=app.open_project("P")
    digest=app.store.current_digest("P")
    preview=app.preview_bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"5"}},
                                                   expected_revisions=expected)
    assert len(preview["rows"])==20 and preview["preview_only"] and not preview["boq_write"]
    assert all(x["old_quantity"]=="6" and x["new_quantity"]=="3" for x in preview["rows"])
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")==before
    app.bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"5"}},
                                 expected_revisions=expected,reason="تغییر مستند گروهی")
    updated=app.load_manual_formulas("P")
    assert all(Decimal(str(updated[key]["quantity"]))==Decimal("3") for key in keys)
    assert app.open_project("P")["boq"]==[]
    with pytest.raises(RuntimeError):
        app.preview_bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"1"}},
                                               expected_revisions=expected)
    app.store.close()


@pytest.mark.parametrize("changes",[
    {"variables":{"not_present":"1"}},
    {"member":"HACK"},
    {"unit":"m2"},
    {"variable_units":{"unknown":"m"}},
])
def test_group_preview_rejects_hidden_identity_or_unknown_fields(tmp_path,changes):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("کنترل","P")
    app.save_manual_formula("P","A",data(),expected_revision=0,reason="ورودی")
    digest=app.store.current_digest("P")
    with pytest.raises(ValueError):
        app.preview_bulk_edit_manual_formulas("P",["A"],changes=changes,
                                               expected_revisions={"A":1})
    assert app.store.current_digest("P")==digest
    app.store.close()


def test_committed_row_is_not_bulk_modified(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("کنترل","P")
    app.save_manual_formula("P","A",data(),expected_revision=0,reason="اول")
    app.review_manual_formula("P","A",expected_revision=1,reviewer="مهندس",note="کنترل")
    app.commit_manual_formula("P","A",expected_revision=1)
    digest=app.store.current_digest("P")
    with pytest.raises(ValueError):
        app.preview_bulk_edit_manual_formulas("P",["A"],changes={"variables":{"length":"4"}},
                                               expected_revisions={"A":1})
    assert app.store.current_digest("P")==digest
    app.store.close()

def test_twenty_member_bulk_undo_redo_uses_original_guarded_history(tmp_path):
    from decimal import Decimal
    app=StructuralProApp(tmp_path/"data")
    app.create_project("ویرایش گروهی","P")
    keys=[]
    for i in range(20):
        key=f"C{i+1}"
        app.save_manual_formula("P",key,data(member=key,source_id="measured:"+key),
                                expected_revision=0,reason="ورودی صریح")
        keys.append(key)
    app.bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"5"}},
                                 expected_revisions={key:1 for key in keys},
                                 reason="تغییر گروهی")
    assert all(Decimal(str(app.load_manual_formulas("P")[k]["quantity"]))==3 for k in keys)
    app.undo_manual_formulas("P")
    assert all(Decimal(str(app.load_manual_formulas("P")[k]["quantity"]))==6 for k in keys)
    app.redo_manual_formulas("P")
    assert all(Decimal(str(app.load_manual_formulas("P")[k]["quantity"]))==3 for k in keys)
    assert app.open_project("P")["boq"]==[]
    app.store.close()


def test_bulk_change_after_other_writer_invalidates_preview_digest(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("هم‌زمان","P")
    app.save_manual_formula("P","A",data(),expected_revision=0,reason="اول")
    preview=app.preview_bulk_edit_manual_formulas("P",["A"],
        changes={"variables":{"length":"7"}},expected_revisions={"A":1})
    concurrent=StructuralProApp(tmp_path/"data")
    concurrent.add_project_floor("P","دوم",level="F2")
    assert app.store.current_digest("P")!=preview["cas_digest"]
    with pytest.raises(RuntimeError):
        app.bulk_edit_manual_formulas("P",["A"],
            changes={"variables":{"length":"7"}},
            expected_revisions={"A":0},reason="نسخه قدیمی")
    assert app.open_project("P")["boq"]==[]
    concurrent.store.close();app.store.close()
