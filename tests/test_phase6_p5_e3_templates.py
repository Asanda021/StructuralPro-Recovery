"""P6-5 E3: SQLite-backed zero-quantity project-start acceptance."""
import pytest
from core.platform.application import StructuralProApp
from core.projects.start_templates import TEMPLATES, preview_project_start, project_payload


@pytest.mark.parametrize("code", list(TEMPLATES))
@pytest.mark.parametrize("count", [1,5,20])
def test_project_start_reopens_without_fake_quantity(tmp_path, code, count):
    app=StructuralProApp(tmp_path/"data")
    pid=f"{code}-{count}"
    preview=app.preview_project_start(code,project_id=pid,name=pid,floor_count=count)
    assert preview["preview_only"] and preview["quantity"] is None
    assert len(preview["floors"])==count
    assert app.store.list()==[]
    saved=app.create_project_from_template(code,project_id=pid,name=pid,floor_count=count)
    assert saved["floors"]==preview["floors"]
    assert saved["members"]==[] and saved["boq"]==[] and saved["takeoffs"]==[]
    assert "estimate" not in saved and "pricebook" not in saved
    assert saved["template_start"]["code"]==code
    app.store.close()
    reopened=StructuralProApp(tmp_path/"data")
    assert reopened.open_project(pid)["floors"]==preview["floors"]
    reopened.store.close()


def test_duplicate_id_and_name_never_overwrite(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    saved=app.create_project_from_template("residential",project_id="P",name="ساختمان",floor_count=5)
    digest=app.store.current_digest("P")
    for pid,name in [("P","دیگر"),("P2","ساختمان")]:
        with pytest.raises(ValueError):
            app.create_project_from_template("industrial",project_id=pid,name=name,floor_count=2)
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")==saved
    assert len(app.store.list())==1
    app.store.close()


@pytest.mark.parametrize("code,count,names",[
    ("wrong",1,None),("residential",0,None),("industrial",-1,None),
    ("commercial",1001,None),("renovation",True,None),
    ("residential",2,["یک"]),("residential",2,["یک","یک"]),
])
def test_invalid_templates_fail_without_creating_project(tmp_path,code,count,names):
    app=StructuralProApp(tmp_path/"data")
    with pytest.raises(ValueError):
        app.create_project_from_template(code,project_id="P",name="آزمایش",floor_count=count,
                                         floor_names=names)
    assert app.store.list()==[]
    app.store.close()


def test_preview_mutation_never_persists(tmp_path):
    preview=preview_project_start("renovation",project_id="R",name="بازسازی",floor_count=2)
    preview["floors"][0]["name"]="دستکاری"
    with pytest.raises(ValueError):
        project_payload(preview)


def test_cas_duplicate_create_only_is_atomic(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("پروژه اصلی","P")
    before=app.store.current_digest("P")
    with pytest.raises(ValueError):
        app.store.save("P",{"id":"P","name":"جایگزین","boq":[]},create_only=True)
    assert app.store.current_digest("P")==before
    assert app.open_project("P")["name"]=="پروژه اصلی"
    app.store.close()
