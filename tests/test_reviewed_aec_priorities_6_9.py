"""Full-building AEC review regression: stairs, shear walls, roofing, finishes and MEP."""
from __future__ import annotations

import copy
import math
import hashlib

import pytest

from core.takeoff.engine import TakeoffEngine
from core.projects.store import ProjectStore
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system, ReviewedAECWorkflow
from core.reports.aec_office_package import audit_boq, prepare_office_rows, export_office_package


_MECHANICAL = {"plumbing", "hvac", "fire_protection"}
_ELECTRICAL = {"electrical_power", "lighting", "low_voltage"}
_VOLUME = {"concrete", "waist_concrete", "step_concrete", "landing_concrete",
           "topping", "ribs", "ribs_x", "ribs_y", "junction_adjustment",
           "gross_concrete", "verified_voids", "deck_concrete",
           "mortar", "adhesive_mortar", "grout", "screed"}
_LENGTH = {"pipes", "cables", "conduits", "trays", "earthing"}
_COUNT = {"blocks", "bricks", "joists", "foam", "studs", "fittings",
          "valves", "equipment", "fixtures", "switches", "devices", "boards"}


def sample(kind: str, *, identity: str = "S1"):
    d = empty_system(kind, "L1", identity)
    d["source"] = {"mode": "manual", "source_id": f"manual:{kind}:L1:{identity}"}
    for name in SPECS[kind].components:
        d["components"][name] = {"status": "not_applicable", "reason": "بازبینی مرجع مستقل",
                                  "source_ref": f"{kind}/{name}/detail",
                                  "approved_by": "مهندس دفتر فنی"}
    for name in SPECS[kind].essential:
        d["components"][name] = component(kind, name)
    return d


def component(kind: str, name: str, *, quantity: float = 1.0, unit: str | None = None):
    if unit is None:
        unit = "m3" if name in _VOLUME else "m" if name in _LENGTH else "عدد" if name in _COUNT else "m2"
    domain = ("mechanical" if kind in _MECHANICAL else
              "electrical" if kind in _ELECTRICAL else "building")
    return {"status": "confirmed", "approved_by": "مهندس مترور",
            "items": [{"line_id": f"{kind}-{name}-1", "mode": "measured",
                       "description": f"{kind}/{name}", "item_code": name,
                       "source_ref": f"schedule/{kind}/{name}",
                       "measurement_ref": f"drawing/{kind}/{name}",
                       "spec_ref": f"approved-specification/{kind}/{name}",
                       "quantity": quantity, "unit": unit, "domain": domain,
                       "formula": "اندازه‌گیری واقعی طبق جدول و جزئیات تأییدشده"}]}


@pytest.mark.parametrize("kind", tuple(SPECS))
def test_all_system_families_have_explicit_measured_and_reviewable_baseline(kind):
    d = sample(kind)
    if kind in {"uboot", "cobiax"}:
        d["components"]["gross_concrete"] = component(kind, "gross_concrete", quantity=3, unit="m3")
        d["components"]["verified_voids"] = component(kind, "verified_voids", quantity=.5, unit="m3")
    if kind == "waffle":
        d["components"]["ribs_y"] = component(kind, "ribs_y", quantity=2, unit="m3")
        d["components"]["junction_adjustment"] = component(kind, "junction_adjustment",
                                                              quantity=.2, unit="m3")
    result = preview_system(d, TakeoffEngine())
    assert result["ready"], (kind, result["blockers"])
    assert result["rows"]
    assert all(r["quantity"] > 0 and r["source_id"] for r in result["rows"])


@pytest.mark.parametrize("kind", ("shear_wall", "stair", "joist_block", "joist_foam",
                                   "waffle", "uboot", "cobiax", "hollow_core",
                                   "steel_deck", "block_wall", "plumbing",
                                   "electrical_power"))
def test_unreviewed_required_groups_block_final_boq(kind):
    d = empty_system(kind, "L1", "S1")
    d["source"] = {"mode": "manual", "source_id": "manual:S1"}
    result = preview_system(d, TakeoffEngine())
    assert not result["ready"]
    assert result["blockers"]


def test_shear_wall_engine_computes_explicit_volume_and_separates_rebar():
    d = sample("shear_wall")
    d["components"]["concrete"] = {
        "status": "confirmed", "approved_by": "checker",
        "items": [{"line_id": "concrete", "mode": "engine", "domain": "building",
                   "item": "shear_wall", "item_code": "concrete",
                   "source_ref": "SW1/drawing", "description": "بتن دیوار برشی",
                   "params": {"length": 5, "thickness": .25, "height": 3, "count": 1}}]}
    d["components"]["vertical_rebar"] = component("shear_wall", "vertical_rebar", quantity=95, unit="kg")
    d["components"]["horizontal_rebar"] = component("shear_wall", "horizontal_rebar", quantity=80, unit="kg")
    report = preview_system(d, TakeoffEngine())
    assert report["ready"], report["blockers"]
    assert next(r for r in report["rows"] if r["component"] == "concrete")["quantity"] == pytest.approx(3.75)
    assert len(report["rows"]) == 3


def test_stair_inclined_waist_not_fake_box_volume():
    d = sample("stair")
    d["components"]["waist_concrete"] = {
        "status": "confirmed", "approved_by": "checker",
        "items": [{"line_id": "waist", "mode": "engine", "domain": "building",
                   "item": "stair_concrete", "item_code": "stair_waist",
                   "source_ref": "ST1/section", "description": "دال شیب‌دار پله",
                   "params": {"sloped_length": 4.0, "width": 1.2,
                              "waist_thickness": .15, "count": 1}}]}
    result = preview_system(d, TakeoffEngine())
    assert result["ready"], result["blockers"]
    assert result["rows"][0]["quantity"] == pytest.approx(.72)


@pytest.mark.parametrize("kind,void", (("uboot", .6), ("cobiax", .8)))
def test_voids_are_subtracted_never_positive_boq_items(kind, void):
    d = sample(kind)
    d["components"]["gross_concrete"] = component(kind, "gross_concrete", quantity=10, unit="m3")
    d["components"]["verified_voids"] = component(kind, "verified_voids", quantity=void, unit="m3")
    rows = preview_system(d, TakeoffEngine())
    assert rows["ready"], rows["blockers"]
    assert len(rows["rows"]) == 1
    assert rows["rows"][0]["quantity"] == pytest.approx(10 - void)
    assert rows["rows"][0]["params"]["deduction"]["quantity_m3"] == pytest.approx(void)


def test_waffle_crossings_subtracted_once():
    d = sample("waffle")
    d["components"]["ribs_y"] = component("waffle", "ribs_y", quantity=4, unit="m3")
    d["components"]["junction_adjustment"] = component("waffle", "junction_adjustment",
                                                         quantity=1, unit="m3")
    out = preview_system(d, TakeoffEngine())
    assert out["ready"], out["blockers"]
    assert next(r for r in out["rows"] if r["component"] == "ribs_y")["quantity"] == 3
    assert all(r["component"] != "junction_adjustment" for r in out["rows"])


def test_void_larger_than_roof_gross_never_commits():
    d = sample("uboot")
    d["components"]["verified_voids"] = component("uboot", "verified_voids",
                                                   quantity=2, unit="m3")
    r = preview_system(d, TakeoffEngine())
    assert not r["ready"]
    assert any("حجم خالص" in msg for msg in r["blockers"])


def test_unreviewed_openings_cannot_be_counted_as_billable_area():
    d = sample("solid_slab")
    d["components"]["openings"] = component("solid_slab", "openings", quantity=4, unit="m2")
    out = preview_system(d, TakeoffEngine())
    assert not out["ready"]
    d["components"]["openings"]["net_excluded_from_quantities"] = True
    out = preview_system(d, TakeoffEngine())
    assert out["ready"], out["blockers"]
    assert all(row["component"] != "openings" for row in out["rows"])


def test_mechanical_and_electrical_domains_cannot_be_mixed():
    d = sample("plumbing")
    d["components"]["pipes"]["items"][0]["domain"] = "building"
    assert not preview_system(d, TakeoffEngine())["ready"]
    d = sample("electrical_power")
    d["components"]["cables"]["items"][0]["domain"] = "mechanical"
    assert not preview_system(d, TakeoffEngine())["ready"]


def test_engine_input_dimensions_and_counts_are_explicit():
    d = sample("shear_wall")
    d["components"]["concrete"] = {
        "status": "confirmed", "approved_by": "checker",
        "items": [{"line_id": "concrete", "mode": "engine", "domain": "building",
                   "item": "shear_wall", "item_code": "concrete",
                   "source_ref": "SW1/drawing", "description": "بتن دیوار برشی",
                   "params": {"length": 5, "thickness": .25, "height": 3}}]}
    result = preview_system(d, TakeoffEngine())
    assert not result["ready"]
    assert any("ناقص" in b for b in result["blockers"])


def test_engine_forbids_unreviewed_complex_roof_formula():
    d = sample("waffle")
    d["components"]["topping"]["items"][0] = {
        "line_id": "wrong", "mode": "engine", "domain": "building",
        "item": "waffle_roof", "item_code": "concrete",
        "source_ref": "detail", "description": "بتن وافل", "params": {}}
    assert not preview_system(d, TakeoffEngine())["ready"]


def test_duplicate_measurement_line_id_is_blocked():
    d = sample("block_wall")
    first = copy.deepcopy(d["components"]["blocks"]["items"][0])
    d["components"]["blocks"]["items"].append(first)
    assert not preview_system(d, TakeoffEngine())["ready"]


def test_no_secret_default_prices_or_quantities():
    d = sample("ceramic_finish")
    d["components"]["tiles"]["items"][0]["quantity"] = float("nan")
    assert not preview_system(d, TakeoffEngine())["ready"]
    d = sample("ceramic_finish")
    d["components"]["tiles"]["items"][0]["quantity"] = -2
    assert not preview_system(d, TakeoffEngine())["ready"]


def _store(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    store.save("P1", {"id": "P1", "name": "نمونه ساختمان", "takeoffs": [], "boq": []})
    return store


def test_sqlite_commit_and_boq_reconciliation(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    d = sample("block_wall")
    entry = wf.save_draft("P1", d)
    assert entry["revision"] == 1
    store.close()
    store = ProjectStore(tmp_path / "projects.db")
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    assert wf.get("P1", "block_wall", "L1", "S1")["revision"] == 1
    info = wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    assert info["takeoff_rows"] == 2
    project = store.get("P1")
    assert len(project["takeoffs"]) == 2
    assert audit_boq(project)["reconciled"]
    with pytest.raises(ValueError, match="قبلاً"):
        wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    store.close()


def test_missing_component_remains_draft_and_does_not_touch_boq(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    d = sample("joist_block")
    d["components"]["blocks"] = {"status": "needs_review"}
    wf.save_draft("P1", d)
    with pytest.raises(ValueError):
        wf.commit("P1", "joist_block", "L1", "S1", expected_revision=1)
    assert not store.get("P1")["boq"]
    store.close()


def test_version_conflict_and_duplicate_cross_system_source(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    d = sample("paint_finish")
    wf.save_draft("P1", d)
    with pytest.raises(RuntimeError):
        wf.save_draft("P1", d, expected_revision=0)
    other = sample("waterproofing")
    other["source"] = copy.deepcopy(d["source"])
    with pytest.raises(ValueError, match="تکرار"):
        wf.save_draft("P1", other)
    store.close()


def test_no_estimate_without_user_pricebook(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    wf.save_draft("P1", sample("block_wall"))
    wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    project = store.get("P1")
    details, cols, meta = prepare_office_rows(project, "takeoff")
    assert len(details) == 2 and not meta["تعداد اقلام بدون قیمت"] == 0
    with pytest.raises(ValueError, match="فهرست‌بها"):
        prepare_office_rows(project, "estimate")
    store.close()


def test_priced_boq_works_only_when_amounts_reconcile(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    wf.save_draft("P1", sample("block_wall"))
    wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    project = store.get("P1")
    imported = tmp_path / "pricebook-import.csv"
    imported.write_text("verified sample rows", encoding="utf-8")
    project["user_pricebook_review"] = {
        "status": "approved", "approved_by": "مسئول برآورد",
        "path": str(imported), "sha256": hashlib.sha256(imported.read_bytes()).hexdigest(),
        "rows_by_code": {},
    }
    for r in project["boq"]:
        r["price_code"] = "USER-" + r["item_code"]
        r["unit_price"] = 100
        r["total"] = r["effective_quantity"] * r["unit_price"] * r["factor"]
        project["user_pricebook_review"]["rows_by_code"][r["price_code"]] = {
            "unit": r["unit"], "unit_price": 100,
        }
    assert audit_boq(project, require_pricebook=True)["pricing_complete"]
    imported.write_text("tampered pricebook", encoding="utf-8")
    with pytest.raises(ValueError, match="تغییر"):
        audit_boq(project, require_pricebook=True)
    imported.write_text("verified sample rows", encoding="utf-8")
    project["boq"][0]["quantity"] += 1
    with pytest.raises(ValueError, match="یکسان"):
        audit_boq(project, require_pricebook=True)
    store.close()


def test_statement_cumulative_quantities_cannot_exceed_takeoff(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    wf.save_draft("P1", sample("block_wall"))
    wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    project = store.get("P1")
    source = project["takeoffs"][0]
    q = source["quantities"][0]
    snapshot = {"status": "approved", "period_id": "1405-07", "approved_by": "checker",
                "previous_quantities_by_source": {source["source_id"]: .75},
                "rows": [{"source_id": source["source_id"], "item_code": q["code"],
                          "description": q["title"], "quantity": .5,
                          "unit": q["unit"], "unit_price": 100, "total": 50}]}
    with pytest.raises(ValueError, match="بیشتر"):
        prepare_office_rows(project, "statement", statement=snapshot)
    snapshot["previous_quantities_by_source"] = {source["source_id"]: .25}
    assert prepare_office_rows(project, "statement", statement=snapshot)[0][0]["total"] == 50
    store.close()


def test_excel_report_is_user_price_safe_and_rtl(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    wf.save_draft("P1", sample("block_wall"))
    wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    output = export_office_package(store.get("P1"), "takeoff", "xlsx",
                                   tmp_path / "office.xlsx")
    wb = openpyxl.load_workbook(output)
    assert wb["ریز متره"].sheet_view.rightToLeft
    assert wb["ریز متره"].max_row >= 4
    store.close()


def test_pricebook_row_unit_and_price_mismatch_are_blocked(tmp_path):
    store = _store(tmp_path)
    wf = ReviewedAECWorkflow(store, TakeoffEngine())
    wf.save_draft("P1", sample("block_wall"))
    wf.commit("P1", "block_wall", "L1", "S1", expected_revision=1)
    project = store.get("P1")
    source = tmp_path / "catalog.csv"
    source.write_bytes(b"reviewed user pricebook bytes")
    project["user_pricebook_review"] = {
        "status": "approved", "approved_by": "مهندس برآورد",
        "path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rows_by_code": {},
    }
    for row in project["boq"]:
        row["unit_price"] = 100
        row["price_code"] = "USER-" + row["item_code"]
        row["total"] = row["effective_quantity"] * 100 * row["factor"]
        project["user_pricebook_review"]["rows_by_code"][row["price_code"]] = {
            "unit": row["unit"], "unit_price": 100}
    assert audit_boq(project, require_pricebook=True)["pricing_complete"]
    project["boq"][0]["unit_price"] = 150
    project["boq"][0]["total"] = project["boq"][0]["effective_quantity"] * 150
    with pytest.raises(ValueError, match="برابر"):
        audit_boq(project, require_pricebook=True)
    store.close()


def test_plumbing_pipe_length_needs_specification_and_length_units():
    d = sample("plumbing")
    d["components"]["pipes"]["items"][0]["unit"] = "m2"
    assert not preview_system(d, TakeoffEngine())["ready"]
    d = sample("plumbing")
    del d["components"]["pipes"]["items"][0]["spec_ref"]
    assert not preview_system(d, TakeoffEngine())["ready"]
    d = sample("plumbing")
    assert preview_system(d, TakeoffEngine())["ready"]


def test_cable_and_light_device_units_are_not_interchangeable():
    d = sample("electrical_power")
    d["components"]["cables"]["items"][0]["unit"] = "عدد"
    assert not preview_system(d, TakeoffEngine())["ready"]
    d = sample("lighting")
    d["components"]["fixtures"]["items"][0]["unit"] = "m"
    assert not preview_system(d, TakeoffEngine())["ready"]
