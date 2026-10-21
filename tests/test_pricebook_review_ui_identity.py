"""A pricebook importer is not an authorized reviewer by default."""
from pathlib import Path
import pytest
from core.platform.application import StructuralProApp


def test_pricebook_form_never_fabricates_reviewer():
    source=Path("app/main.py").read_text(encoding="utf-8")
    assert 'price_reviewer.setObjectName("PricebookReviewer")' in source
    assert 'reviewer=price_reviewer.text().strip()' in source
    assert 'if bound_project and not reviewer:' in source
    assert 'approved_by=reviewer' in source
    assert 'approved_by="کاربر واردکننده فهرست‌بها"' not in source
    assert "فقط کتابخانه؛ تأیید مالی پروژه انجام نشده" in source


def test_import_project_pricebook_rejects_missing_reviewer_without_mutation(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("پروژه آزمایشی","P")
    path=tmp_path/"reviewed.csv"
    path.write_text("year,group,chapter,code,description,unit,unit_price\n1405,ابنیه,01,C01,بتن,m3,100\n",encoding="utf-8")
    before=app.open_project("P")
    for reviewer in ("", "   ", None):
        with pytest.raises(ValueError,match="تأییدکننده"):
            app.import_project_pricebook("P",path,year=1405,approved_by=reviewer)
        assert app.open_project("P")==before
    app.store.close()
