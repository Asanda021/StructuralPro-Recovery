"""Fail-closed stirrup stations, end/middle/end zones, SQLite and BOQ tests."""
import pytest

from core.takeoff.stirrup_zones import validate_stirrup_zones
from core.takeoff.beam_detail import preview_beam, empty_beam, BeamDetailWorkflow
from core.takeoff.engine import TakeoffEngine
from core.projects.store import ProjectStore


def valid():
    return [
        {"name": "ابتدا", "start_m": 0, "end_m": 1.2, "spacing_m": .1,
         "first_bar_m": .05, "last_bar_m": 1.15, "count": 12,
         "cut_length_m": 1.3, "unit_weight_kg_m": .395, "source_ref": "B1/section/end"},
        {"name": "میانه", "start_m": 1.2, "end_m": 3.8, "spacing_m": .2,
         "first_bar_m": 1.3, "last_bar_m": 3.7, "count": 13,
         "cut_length_m": 1.35, "unit_weight_kg_m": .395, "source_ref": "B1/section/mid"},
        {"name": "انتها", "start_m": 3.8, "end_m": 5, "spacing_m": .1,
         "first_bar_m": 3.85, "last_bar_m": 4.95, "count": 12,
         "cut_length_m": 1.3, "unit_weight_kg_m": .395, "source_ref": "B1/section/end2"},
    ]


def complete_beam():
    d = empty_beam("L1", "B1")
    d["source"] = {"mode": "manual", "source_id": "manual:P1:L1:B1"}
    d["geometry"] = {"length": 5, "width": .3, "depth": .5, "count": 1,
                     "deductions_m3": 0, "approved_by": "مدیر فنی", "source_ref": "B1/section"}
    d["formwork"] = {"net_area_m2": 6, "approved_by": "مدیر فنی", "source_ref": "B1/formwork"}
    for k in d["bars"]:
        d["bars"][k] = {"status": "not_applicable", "approved_by": "مدیر فنی",
                        "source_ref": f"B1/{k}", "reason": "در دیتایل وجود ندارد"}
    d["bars"]["stirrups"] = {"status": "confirmed", "approved_by": "مدیر فنی",
                              "source_ref": "B1/stirrup-detail", "segments": valid()}
    return d


def test_three_zone_reviewed_quantities_exact():
    z = validate_stirrup_zones(valid(), 5)
    assert sum(x["count"] for x in z) == 37
    out = preview_beam(complete_beam(), TakeoffEngine())
    assert out["ready"], out["blockers"]
    row = next(x for x in out["rows"] if x["source_id"].endswith("stirrups"))
    assert row["quantity"] == pytest.approx((24*1.3+13*1.35)*.395)
    assert len(row["params"]["segments"]) == 3
    assert row["params"]["segments"][0]["first_bar_m"] == .05


@pytest.mark.parametrize("key,val,match", [
    ("end_m",1.5,"پوشش|هم‌پوشانی|مرز"),
    ("end_m",1.1,"خارج از ناحیه|پوشش|هم‌پوشانی"),
    ("start_m",.1,"خارج از ناحیه|ابتدای تیر"),
    ("first_bar_m",-.1,"اولین"),
    ("last_bar_m",1.21,"خارج از ناحیه|تعداد"),
    ("count",13,"تعداد"),
    ("spacing_m",.12,"تعداد"),
    ("cut_length_m",0,"طول برش"),
    ("unit_weight_kg_m",float("nan"),"وزن واحد"),
    ("source_ref","","مرجع"),
])
def test_reject_zone_tampering(key,val,match):
    z = valid()
    z[0][key] = val
    with pytest.raises(ValueError, match=match):
        validate_stirrup_zones(z, 5)


def test_reject_zone_overlap_and_gap():
    for a in (1.1, 1.3):
        z = valid()
        z[1]["start_m"] = a
        with pytest.raises(ValueError, match="هم‌پوشانی|فاصله|مرز"):
            validate_stirrup_zones(z, 5)


def test_reject_double_count_on_shared_boundary():
    z = valid()
    z[0].update(first_bar_m=.1, last_bar_m=1.2)
    z[1].update(first_bar_m=1.2, last_bar_m=3.6)
    with pytest.raises(ValueError, match="مشترک"):
        validate_stirrup_zones(z, 5)


def test_reject_uncovered_beam_tail():
    z = valid()
    z[-1]["end_m"] = 4.99
    with pytest.raises(ValueError, match="انتهای تیر"):
        validate_stirrup_zones(z, 5)


def test_empty_segment_blocks_commit():
    d = complete_beam()
    d["bars"]["stirrups"]["segments"] = []
    report = preview_beam(d, TakeoffEngine())
    assert not report["ready"]
    assert any("خاموت" in b for b in report["blockers"])


def test_unreviewed_stirrup_zones_are_not_final():
    d = complete_beam()
    d["bars"]["stirrups"]["status"] = "needs_review"
    report = preview_beam(d, TakeoffEngine())
    assert not report["ready"]
    assert all(not r["source_id"].endswith("stirrups") for r in report["rows"])


def test_sqlite_zones_roundtrip_and_stale_revision(tmp_path):
    path = tmp_path/"projects.db"
    store = ProjectStore(path)
    store.save("P1", {"id": "P1", "name": "آزمون", "takeoffs": [], "boq": []})
    wf = BeamDetailWorkflow(store, TakeoffEngine())
    d = complete_beam()
    result = wf.save_draft("P1", d)
    store.close()
    store = ProjectStore(path)
    wf = BeamDetailWorkflow(store, TakeoffEngine())
    assert wf.get("P1","L1","B1")["data"]["bars"]["stirrups"]["segments"] == valid()
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        wf.commit("P1", "L1", "B1", expected_revision=result["revision"] + 1)
    assert not store.get("P1")["boq"]
    ok = wf.commit("P1", "L1", "B1", expected_revision=result["revision"])
    assert ok["status"] == "committed"
    assert len(store.get("P1")["boq"]) > 0
    with pytest.raises(ValueError, match="قبلاً"):
        wf.commit("P1", "L1", "B1", expected_revision=result["revision"])
    store.close()


def test_reject_persian_numbers_in_count_if_fraction():
    z = valid()
    z[1]["count"] = "۱۳.۵"
    with pytest.raises(ValueError, match="صحیح"):
        validate_stirrup_zones(z, 5)


def test_accept_unsorted_zones_but_sorted_deterministically():
    z = valid()
    z.reverse()
    out = validate_stirrup_zones(z, 5)
    assert [item["name"] for item in out] == ["ابتدا", "میانه", "انتها"]
