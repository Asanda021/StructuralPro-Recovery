"""P7 P4: genuinely approved, exact and currency-explicit financial impact.

Every positive sample uses the live ProjectStore revision history and the
real source CSV reviewed by the existing pricebook importer.
"""
from copy import deepcopy
from decimal import Decimal
import json

import pytest
from core.platform.application import StructuralProApp
from core.reports.technical_office_revision import (
    preview_revision_quantity_changes, export_revision_quantity_package,
)


def _approved_revisions(tmp_path, *, currency="IRR"):
    a = StructuralProApp(tmp_path / "db")
    a.create_project("مصالح با نرخ مستند مصنوعی", "P")
    a.add_takeoff("P", "building", "wall", source_id="manual:W1",
                  system="L1", length=10, height=3, count=1,
                  openings=0, price_code="W", unit_price=100)
    price_file = tmp_path / "reviewed-rates.csv"
    price_file.write_text(
        "year,group,chapter,code,description,unit,unit_price\n"
        "1405,ابنیه,01,W,دیوار,m2,100\n", encoding="utf-8",
    )
    a.import_project_pricebook("P", price_file, year=1405,
                               approved_by="independent-fixture-reviewer",
                               currency=currency, source_version="v1")
    before = a.open_project("P")["_meta"]["version"]
    a.revise_takeoff("P", "manual:W1", expected_revision=1,
                     domain="building", item="wall", system="L1",
                     length=12, height=3, count=1, openings=0,
                     price_code="W", unit_price=100)
    after = a.open_project("P")["_meta"]["version"]
    return a, before, after, price_file


def test_real_pricebook_quantity_delta_is_only_financial_when_explicitly_requested(tmp_path):
    app, before, after, source = _approved_revisions(tmp_path)
    original = app.open_project("P")
    digest = app.store.current_digest("P")
    kw = dict(project_id="P", before_version=before, after_version=after)
    try:
        plain = preview_revision_quantity_changes(app, **kw)
        assert plain["financial_impact"] is None
        reviewed = preview_revision_quantity_changes(
            app, **kw, include_verified_financial_impact=True)
        effect = reviewed["financial_impact"]
        assert effect["currency"] == "IRR"
        assert effect["amount"] == "600"
        assert effect["status"] == "VERIFIED_QUANTITY_ONLY_EFFECT_NOT_PAYMENT_CERTIFICATE"
        assert Decimal(reviewed["rows"][0]["مقدار قبلی"]) == 30
        assert Decimal(reviewed["rows"][0]["مقدار جدید"]) == 36
        assert Decimal(reviewed["rows"][0]["اختلاف مقدار"]) == 6
        assert "quantity_only" in effect["basis"]
        assert digest == app.store.current_digest("P")
        assert original == app.open_project("P")
    finally:
        app.store.close()


def test_approved_money_effect_is_exported_to_manifest_without_sqlite_write(tmp_path):
    app, before, after, source = _approved_revisions(tmp_path)
    kw = dict(project_id="P", before_version=before, after_version=after)
    dest = tmp_path / "approved-monetary-quantity-comparison"
    start_digest = app.store.current_digest("P")
    try:
        output = export_revision_quantity_package(
            app, **kw, expected_current_version=after, destination=dest,
            include_verified_financial_impact=True)
        manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
        assert manifest == output["manifest"]
        assert manifest["financial_impact"]["amount"] == "600"
        assert manifest["financial_impact"]["currency"] == "IRR"
        assert manifest["readonly"] is True
        assert app.store.current_digest("P") == start_digest
    finally:
        app.store.close()


def test_explicit_undefined_currency_remains_unknown_not_zero(tmp_path):
    app, before, after, source = _approved_revisions(tmp_path, currency=None)
    try:
        r = preview_revision_quantity_changes(
            app, project_id="P", before_version=before, after_version=after,
            include_verified_financial_impact=True)
        assert r["financial_impact"] is None
        assert r["financial_impact_status"] == "NOT_DETERMINABLE_WITHOUT_APPROVED_PRICES"
    finally:
        app.store.close()


def test_modified_real_price_source_fails_closed(tmp_path):
    app, before, after, source = _approved_revisions(tmp_path)
    try:
        source.write_text(source.read_text(encoding="utf-8") + "1405,ابنیه,01,X,غیرمجاز,m2,1\n",
                          encoding="utf-8")
        with pytest.raises(ValueError):
            preview_revision_quantity_changes(
                app, project_id="P", before_version=before, after_version=after,
                include_verified_financial_impact=True)
    finally:
        app.store.close()


@pytest.mark.parametrize("field,value", [
    ("factor", "1.5"), ("unit_price", "110"),
    ("price_code", "X"), ("effective_quantity", "999"),
])
def test_changed_priced_bo_q_receipt_never_produces_verified_impact(tmp_path,monkeypatch,field,value):
    app, before, after, source = _approved_revisions(tmp_path)
    real = app.store.revisions
    def forged(pid):
        data = real(pid)
        item = next(z for z in data if z["version"] == after)
        item["payload"]["boq"][0][field] = value
        return data
    monkeypatch.setattr(app.store, "revisions", forged)
    try:
        with pytest.raises(ValueError):
            preview_revision_quantity_changes(
                app, project_id="P", before_version=before, after_version=after,
                include_verified_financial_impact=True)
    finally:
        app.store.close()


def test_missing_current_source_only_returns_unknown_when_not_verified(tmp_path):
    app, before, after, source = _approved_revisions(tmp_path)
    try:
        # Input of the actual historical pair without price checks always
        # remains amount-agnostic for the default quantity-only report.
        result = preview_revision_quantity_changes(
            app, project_id="P", before_version=before, after_version=after)
        assert result["financial_impact"] is None
        assert result["readonly"]
    finally:
        app.store.close()
