"""Review-only rebar callout proposal tests; no automatic quantity endorsement."""
from dataclasses import replace
import pytest
from core.drawings.beam_detail_match import BeamEvidence
from core.drawings.beam_rebar_hints import propose_rebar_from_evidence


def sample(text, ref="pdf:page:2:line:10"):
    return BeamEvidence(ref, text, "pdf", 2)


def test_longitudinal_count_and_diameter_from_explicit_callout():
    out = propose_rebar_from_evidence([sample("B1 میلگرد طولی: ۴Φ۲۰")], "b۱")
    p = out["candidates"][0]
    assert (p["kind"], p["count"], p["diameter_mm"]) == ("longitudinal", 4, 20)
    assert not out["ready_for_boq"] and not p["quantity_approved"]


def test_stirrup_spacing_explicit_unit_not_a_quantity():
    p = propose_rebar_from_evidence([sample("B1 خاموت: Φ8 @ 15 cm")], "B1")["candidates"][0]
    assert p["spacing_m"] == pytest.approx(.15)
    assert p["count"] is None and p["issues"]


def test_stirrup_spacing_without_unit_is_not_assumed():
    p = propose_rebar_from_evidence([sample("B1 خاموت: Ø8 @15")], "B1")["candidates"][0]
    assert p["spacing_m"] is None and any("واحد" in x for x in p["issues"])


def test_persian_digit_and_english_label():
    p = propose_rebar_from_evidence([sample("b۱ LONGITUDINAL: 2Ø16")], "B1")["candidates"][0]
    assert p["count"] == 2 and p["diameter_mm"] == 16


def test_extra_bar_categories_are_not_merged():
    texts = ["B1 کمرکش: 2Φ12", "B1 سنجاقی: 6Φ8", "B1 تقویتی: 2Φ18"]
    out = propose_rebar_from_evidence([sample(x, f"cad:page:1:handle:{i}") for i,x in enumerate(texts)], "B1")
    assert {x["kind"] for x in out["candidates"]} == {"side_bars", "crossties", "additional"}


def test_no_beam_id_and_no_category_never_inferred():
    out = propose_rebar_from_evidence([sample("4Ø20"), sample("B1 4Ø20")], "B1")
    assert out["candidates"] == []


def test_no_false_match_to_b10():
    assert propose_rebar_from_evidence([sample("B10 خاموت Φ8 @10cm")], "B1")["candidates"] == []


def test_two_beams_in_same_line_rejected():
    out = propose_rebar_from_evidence([sample("B1 B2 میلگرد طولی: 4Φ20")], "B1")
    assert out["candidates"] == [] and out["warnings"]


def test_multiple_diameters_in_one_series_rejected():
    out = propose_rebar_from_evidence([sample("B1 میلگرد طولی: 4Φ20 + 2Φ16")], "B1")
    assert out["candidates"] == []


def test_bare_diameter_without_type_not_labeled():
    out = propose_rebar_from_evidence([sample("B1 Ø20")], "B1")
    assert not out["candidates"]


def test_separate_stirrup_zones_are_review_candidates_not_summed():
    out = propose_rebar_from_evidence([sample("B1 خاموت: Φ8 @10cm; B1 خاموت: Φ8 @15cm")], "B1")
    assert len(out["candidates"]) == 2 and out["warnings"] and not out["ready_for_boq"]


def test_missing_source_fails_closed():
    with pytest.raises(ValueError, match="مرجع"):
        propose_rebar_from_evidence([sample("B1 طولی 4Φ20", "")], "B1")


def test_bad_page_fails_closed():
    with pytest.raises(ValueError, match="صفحه"):
        propose_rebar_from_evidence([replace(sample("B1 طولی: 4Φ20"), page=0)], "B1")


def test_invalid_tag_is_rejected():
    with pytest.raises(ValueError, match="شناسه"):
        propose_rebar_from_evidence([sample("B1 طولی: 4Φ20")], "")


def test_duplicate_evidence_is_not_summed():
    out = propose_rebar_from_evidence([
        sample("B1 میلگرد طولی 4Φ20"),
        sample("B1 میلگرد طولی 4Φ20", ref="pdf:page:2:line:11"),
    ], "B1")
    assert len(out["candidates"]) == 2 and any("چند سری" in x for x in out["warnings"])


def test_stirrup_explicit_count_is_still_not_approved():
    p = propose_rebar_from_evidence([sample("B1 خاموت: 34Φ8 @15cm")], "B1")["candidates"][0]
    assert p["count"] == 34 and not p["quantity_approved"]


def test_suggested_values_are_not_committable_quantities():
    from core.takeoff.beam_detail import empty_beam, preview_beam
    from core.takeoff.engine import TakeoffEngine
    proposed = propose_rebar_from_evidence([sample("B1 میلگرد طولی: 4Φ20")], "B1")["candidates"][0]
    draft = empty_beam("L1", "B1")
    draft["bars"]["longitudinal"] = {
        "status": "needs_review", "count": proposed["count"],
        "nominal_diameter_mm": proposed["diameter_mm"], "source_ref": proposed["source_ref"]
    }
    report = preview_beam(draft, TakeoffEngine())
    assert not report["ready"]
    assert not any(row["code"] == "rebar" for row in report["rows"])


def test_sqlite_draft_keeps_rebar_hint_but_never_commits_it(tmp_path):
    from core.takeoff.beam_detail import empty_beam, BeamDetailWorkflow
    from core.takeoff.engine import TakeoffEngine
    from core.projects.store import ProjectStore
    path = tmp_path / "projects.db"
    store = ProjectStore(path)
    store.save("P1", {"id": "P1", "name": "آزمون", "takeoffs": [], "boq": []})
    draft = empty_beam("L1", "B1")
    draft["source"] = {"mode": "manual", "source_id": "manual:P1:L1:B1"}
    draft["bars"]["longitudinal"] = {
        "status": "needs_review", "count": 4, "nominal_diameter_mm": 20,
        "source_ref": "pdf:page:2:line:10",
    }
    workflow = BeamDetailWorkflow(store, TakeoffEngine())
    entry = workflow.save_draft("P1", draft)
    store.close()
    restored = ProjectStore(path)
    after = BeamDetailWorkflow(restored, TakeoffEngine())
    assert after.get("P1", "L1", "B1")["data"]["bars"]["longitudinal"]["count"] == 4
    with pytest.raises(ValueError, match="ناقص"):
        after.commit("P1", "L1", "B1", expected_revision=entry["revision"])
    assert restored.get("P1")["boq"] == []
    restored.close()


def test_dxf_vector_text_roundtrip_yields_unapproved_bar_hint(tmp_path):
    from types import SimpleNamespace
    ezdxf = pytest.importorskip("ezdxf")
    from core.drawings.beam_detail_match import cad_beam_evidence
    path = tmp_path / "b1-bars.dxf"
    drawing = ezdxf.new()
    drawing.modelspace().add_text("B1 LONGITUDINAL: 4Ø20", dxfattribs={"insert": (110, 190)})
    drawing.modelspace().add_text("B10 STIRRUP: Ø8 @10cm", dxfattribs={"insert": (120, 200)})
    drawing.saveas(path)
    reopened = ezdxf.readfile(path)
    entities = [SimpleNamespace(entity_type=e.dxftype(), layer=e.dxf.layer,
                 handle=e.dxf.handle, data={"text": e.dxf.text,
                     "insert": (e.dxf.insert.x, e.dxf.insert.y)}) for e in reopened.modelspace()]
    matched = cad_beam_evidence(SimpleNamespace(entities=entities), "B1",
                                region=(8, 8, 5, 5), scene_origin=(100, 200))
    hints = propose_rebar_from_evidence(matched, "B1")
    assert len(hints["candidates"]) == 1
    assert hints["candidates"][0]["count"] == 4
    assert hints["candidates"][0]["diameter_mm"] == 20
    assert not hints["quantity_approved"] and not hints["ready_for_boq"]


def test_invalid_draft_diameter_or_count_is_refused():
    from core.takeoff.beam_detail import empty_beam, preview_beam
    from core.takeoff.engine import TakeoffEngine
    draft = empty_beam("L1", "B1")
    draft["bars"]["longitudinal"] = {"status": "needs_review", "count": -2}
    with pytest.raises(ValueError, match="تعداد"):
        preview_beam(draft, TakeoffEngine())
    draft["bars"]["longitudinal"] = {"status": "needs_review", "nominal_diameter_mm": 0}
    with pytest.raises(ValueError, match="قطر"):
        preview_beam(draft, TakeoffEngine())
