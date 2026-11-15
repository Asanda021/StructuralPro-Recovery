"""Synthetic evidence for the combined geometry and cross-sheet PDF intake."""
from hashlib import sha256

import pymupdf
import pytest

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def sheets(tmp_path, name, specs):
    path = tmp_path / name
    with pymupdf.open() as pdf:
        for spec in specs:
            page = pdf.new_page(width=720, height=440)
            for x, y, text in spec.get("text", ()):
                page.insert_text((x, y), text, fontsize=9)
            for coords in spec.get("boxes", ()):
                page.draw_rect(pymupdf.Rect(*coords))
            page.set_rotation(spec.get("rotation", 0))
        pdf.save(path)
    return path


def registry(*entries):
    return {
        "schema_version": 1,
        "documents": [
            {"sha256": sha256(path.read_bytes()).hexdigest(), "project_id": project,
             "issue_id": "ISSUE-1", "revision": revision, "status": status,
             "authority_reference": "Synthetic issue register, row " + str(n)}
            for n, (path, project, revision, status) in enumerate(entries, 1)
        ],
    }


def plan(tmp_path, name="plan.pdf", sheet="S-101", *, member="I-01", tag="B1",
         grid="A/1", level="L1", target="S-201", detail="D-1", revision="R1"):
    return sheets(tmp_path, name, [
        {"text": [(24, 25, f"SHEET {sheet} | REV {revision}"), (24, 45, "BEAM PLAN"),
                  (24, 155, f"INSTANCE {member} TYPE {tag} GRID {grid} LEVEL {level}"),
                  (24, 315, f"FOR INSTANCE {member} DETAIL {detail} / {target}")],
         "boxes": [(24, 85, 104, 141)]},
    ])


def details(tmp_path, name="details.pdf", *, tag="B1", family="Beam", revision="R1"):
    return sheets(tmp_path, name, [
        {"text": [(24, 25, f"SHEET S-201 | REV {revision}"),
                  (26, 150, f"DETAIL D-1 {family} {tag}"), (36, 169, "SCALE 1:20"),
                  (332, 150, "DETAIL D-2 Column C1"), (340, 169, "SCALE 1:50")],
         "rotation": 90,
         "boxes": [(3, 3, 715, 434), (28, 85, 105, 137),
                   (330, 85, 400, 137), (565, 87, 630, 145)]},
    ])


def graph(paths, register=None, **kwargs):
    options = {"revision_registry": register} if register is not None else {}
    value = inspect_pdf_sheet_set(paths, **options, **kwargs)["detail_evidence_graph"]
    assert value["quantity_approval_count"] == 0
    assert value["physical_member_count"] is None
    assert value["acceptance"] == "PARTIAL_NO_GO"
    assert all(edge["financially_payable"] is False for edge in value["edges"])
    return value


def of(items, key, value):
    return [item for item in items if item.get(key) == value]


def test_two_geometry_details_and_one_untitled_on_rotated_multi_scale_sheet(tmp_path):
    value = graph([details(tmp_path)])
    assert len(value["pages"]) == 1 and value["pages"][0]["rotation"] == 90
    contours = of(value["nodes"], "kind", "VIEW")
    titled = {item["detail_code"]: item for item in contours if item.get("detail_code")}
    assert set(titled) == {"D-1", "D-2"}
    assert titled["D-1"]["printed_scale"] == "1:20"
    assert titled["D-2"]["printed_scale"] == "1:50"
    assert {titled[k]["family"] for k in titled} == {"beam", "column"}
    assert sum(item.get("detail_code") is None for item in contours) >= 1
    assert any(item["reason_code"] == "UNTITLED_CONTOUR" for item in value["issues"])
    assert not of(value["nodes"], "kind", "INSTANCE_CANDIDATE")


def test_approved_issue_gives_explicit_reference_without_member_payment(tmp_path):
    p, d = plan(tmp_path), details(tmp_path)
    r = registry((p, "P-1", "R1", "CURRENT"), (d, "P-1", "R1", "CURRENT"))
    value = graph([p, d], r)
    link, = of(value["edges"], "relationship", "DETAIL_CALLOUT")
    assert link["status"] == "VALIDATED_REFERENCE"
    nodes = {n["node_id"]: n for n in value["nodes"]}
    assert nodes[link["source_id"]]["kind"] == "INSTANCE_CANDIDATE"
    assert nodes[link["target_id"]]["detail_code"] == "D-1"
    assert {a["document_id"] for a in link["anchors"]} == {"PDF001", "PDF002"}
    assert sum(n["kind"] == "TYPE_DEFINITION" and n["type_tag"] == "B1" for n in nodes.values()) == 1
    assert any(i["reason_code"] == "MISSING_INDEPENDENT_LEVEL" for i in value["issues"])
    assert any(i["reason_code"] == "MISSING_INDEPENDENT_AXIS" for i in value["issues"])


@pytest.mark.parametrize("change,reason", [
    ("unregistered", "UNVERIFIED_DOCUMENT_SCOPE"),
    ("foreign", "DIFFERENT_PROJECT_OR_ISSUE"),
    ("superseded", "SUPERSEDED_SOURCE"),
    ("revision", "REVISION_CONFLICT"),
    ("family", "TYPE_FAMILY_CONFLICT"),
    ("wrong_sheet", "REFERENCE_TARGET_NOT_FOUND"),
])
def test_explicit_references_do_not_route_around_scope_and_identity(tmp_path, change, reason):
    p = plan(tmp_path, target="S-900" if change == "wrong_sheet" else "S-201")
    d = details(tmp_path, family="Column" if change == "family" else "Beam",
                revision="R2" if change == "revision" else "R1")
    reg = registry((p, "P-1", "R1", "CURRENT"),
                   (d, "P-2" if change == "foreign" else "P-1",
                    "R2" if change == "revision" else "R1",
                    "SUPERSEDED" if change == "superseded" else "CURRENT"))
    value = graph([p, d], None if change == "unregistered" else reg)
    link, = of(value["edges"], "relationship", "DETAIL_CALLOUT")
    assert link["status"] in {"BLOCKED", "REJECTED"}
    assert link["reason_code"] == reason


def test_same_explicit_instance_in_plan_and_section_keeps_one_candidate(tmp_path):
    p = plan(tmp_path)
    s = sheets(tmp_path, "section.pdf", [
        {"text": [(24, 25, "SHEET S-401 | REV R1"), (26, 50, "SECTION A-A"),
                  (24, 160, "INSTANCE I-01 TYPE B1 GRID A/1 LEVEL L1"), (24, 260, "LEVEL L1")],
         "boxes": [(24, 86, 100, 146)]},
    ])
    axis = sheets(tmp_path, "axes.pdf", [
        {"text": [(24, 25, "SHEET S-402 | REV R1"), (24, 53, "AXIS PLAN"),
                  (24, 160, "GRID A/1")]},
    ])
    p2 = plan(tmp_path, "second-level.pdf", "S-102", level="L2")
    reg = registry(*[(path, "P-1", "R1", "CURRENT") for path in (p, s, axis, p2)])
    value = graph([p, s, axis, p2], reg)
    items = of(value["nodes"], "kind", "INSTANCE_CANDIDATE")
    assert {node["level"] for node in items} == {"L1", "L2"}
    first, = of(items, "level", "L1")
    assert len(first["anchors"]) >= 2
    assert first["identity_witness_count"] == 2
    witnesses = of(value["edges"], "source_id", first["node_id"])
    assert any(e["relationship"] == "AT_AXIS" and e["status"] == "VALIDATED_REFERENCE" for e in witnesses)
    assert any(e["relationship"] == "AT_LEVEL" and e["status"] == "VALIDATED_REFERENCE" for e in witnesses)
    assert value["floor_repetition_multiplier"] is None
    swapped = graph([p2, axis, s, p], reg)
    assert {n["node_id"] for n in value["nodes"]} == {n["node_id"] for n in swapped["nodes"]}


def test_competing_explicit_occurrence_locations_block_instead_of_multiplying(tmp_path):
    a, b = plan(tmp_path), plan(tmp_path, "other.pdf", "S-102", grid="B/2")
    value = graph([a, b], registry(*[(p, "P-1", "R1", "CURRENT") for p in (a, b)]))
    item, = of(value["nodes"], "kind", "INSTANCE_CANDIDATE")
    assert item["status"] == "BLOCKED" and item["identity_witness_count"] == 2
    assert any(issue["reason_code"] == "INSTANCE_SCOPE_CONFLICT" for issue in value["issues"])


def test_missing_stale_and_duplicate_sources_fail_without_publishable_graph(tmp_path, monkeypatch):
    import core.drawings.pdf_auto_intake as intake

    source = plan(tmp_path)
    replacement = plan(tmp_path, "replacement.pdf", revision="R2")
    copy = tmp_path / "copy.pdf"
    copy.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="Duplicate"):
        graph([source, copy])
    stale = registry((replacement, "P", "R2", "CURRENT"))
    with pytest.raises(ValueError, match="(?i)(sha|source|registry)"):
        graph([source], stale)
    real_open = pymupdf.open

    def swap(*args, **kwargs):
        if kwargs.get("stream") is not None and replacement.exists():
            replacement.replace(source)
        return real_open(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pymupdf, "open", swap)
        with pytest.raises(ValueError, match="(منبع|source)"):
            intake.inspect_pdf_sheet_set([source])


def test_scanned_page_is_visible_in_graph_with_explicit_missing_ocr(tmp_path):
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 16, 16), False)
        image.clear_with(40)
        page.insert_image(page.rect, pixmap=image)
        pdf.save(path)
    value = graph([path])
    page, = value["pages"]
    assert page["status"] == "BLOCKED"
    assert any(issue["reason_code"] == "RASTER_SEMANTICS_UNVERIFIED" for issue in value["issues"])
    assert not of(value["nodes"], "kind", "INSTANCE_CANDIDATE")


def test_distinct_families_covered_with_no_member_inference(tmp_path):
    cases = [
        ("Column C1", "column"), ("Girder B1", "beam"), ("Footing F1", "foundation"),
        ("Slab T1", "slab_roof"), ("Window W1", "wall_opening"), ("Ramp ST1", "stair_ramp"),
        ("Reinforcement R1", "reinforcement_connection"), ("Architectural finish A1", "architecture_finishes"),
        ("Mechanical duct M1", "mechanical"), ("Electrical wiring E1", "electrical"),
        ("Unlabeled form U1", "unknown"),
    ]
    source = sheets(tmp_path, "separate-families.pdf", [
        {"text": [(50, 140, f"DETAIL D-{index} {title}")], "boxes": [(50, 50, 180, 132)]}
        for index, (title, _) in enumerate(cases, 1)
    ])
    value = graph([source])
    views = {node["detail_code"]: node for node in of(value["nodes"], "kind", "VIEW")}
    assert [views[f"D-{i}"]["family"] for i in range(1, len(cases) + 1)] == [family for _, family in cases]
    assert views[f"D-{len(cases)}"]["status"] == "UNRESOLVED"
    assert not of(value["nodes"], "kind", "INSTANCE_CANDIDATE")


def test_same_type_multiple_details_and_occurrences_keep_floor_specific_schedule_conflict(tmp_path):
    a = plan(tmp_path)
    b = plan(tmp_path, "another-location.pdf", "S-102", member="I-02", grid="B/2")
    c = plan(tmp_path, "other-level.pdf", "S-103", level="L2", detail="D-2")
    d = sheets(tmp_path, "two-variants.pdf", [
        {"text": [(24, 25, "SHEET:S-201 | REV:R1"),
                  (35, 149, "DETAIL D-1 Beam B1"), (350, 149, "DETAIL D-2 Beam B1")],
         "boxes": [(24, 85, 104, 141), (346, 85, 425, 141)]},
    ])
    schedule = sheets(tmp_path, "schedule.pdf", [
        {"text": [(24, 25, "SHEET S-501 | REV R1"), (24, 65, "BEAM SCHEDULE"),
                  (24, 120, "SCHEDULE ROW TYPE B1 LEVEL L1 DETAIL D-2 / S-201"),
                  (24, 160, "SCHEDULE ROW TYPE B1 LEVEL L2 DETAIL D-2 / S-201")]},
    ])
    sources = [a, b, c, d, schedule]
    value = graph(sources, registry(*[(p, "P-1", "R1", "CURRENT") for p in sources]))
    assert len(of(value["nodes"], "kind", "TYPE_DEFINITION")) == 1
    assert len(of(value["edges"], "relationship", "DETAIL_TYPE_DEFINITION")) == 2
    assert len(of(value["nodes"], "kind", "INSTANCE_CANDIDATE")) == 3
    matches = [e for e in value["edges"] if e["relationship"].endswith("DETAIL_CALLOUT")]
    assert [e["status"] for e in matches].count("VALIDATED_REFERENCE") == 2
    conflicting = of(matches, "reason_code", "CONFLICTING_DETAIL_REFERENCES")
    assert len(conflicting) == 3 and all(e["status"] == "AMBIGUOUS" for e in conflicting)
    assert value["floor_repetition_multiplier"] is None


def test_one_word_two_shapes_two_words_one_shape_and_ambiguous_heading(tmp_path):
    p = sheets(tmp_path, "ambiguous.pdf", [
        {"text": [(87, 91, "B1")], "boxes": [(36, 54, 78, 112), (110, 54, 148, 112)]},
        {"text": [(67, 80, "B1"), (67, 100, "B2")], "boxes": [(31, 55, 141, 120)]},
        {"text": [(33, 141, "DETAIL D-1 Beam B1 B2")], "boxes": [(31, 55, 141, 132)]},
    ])
    value = graph([p])
    edges = of(value["edges"], "relationship", "TYPE_WORD_NEAR_VIEW")
    assert len(edges) == 3 and all(e["status"] == "AMBIGUOUS" for e in edges)
    assert sorted(len(e["candidate_ids"]) for e in edges) == [1, 1, 2]
    assert len(of(value["issues"], "reason_code", "MULTIPLE_DETAIL_TYPE_MARKS")) == 1
    assert len(value["review_questions"]) == 3
    assert not of(value["nodes"], "kind", "TYPE_DEFINITION")
    assert not of(value["nodes"], "kind", "INSTANCE_CANDIDATE")


def test_page_reader_fault_keeps_page_while_link_budget_blocks_partial_results(tmp_path, monkeypatch):
    import core.drawings.pdf_detail_evidence_graph as evidence

    source = details(tmp_path)
    original_get_text = pymupdf.Page.get_text

    def fail_dict(self, option="text", *args, **kwargs):
        if option == "dict":
            raise RuntimeError("synthetic page extraction failure")
        return original_get_text(self, option, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pymupdf.Page, "get_text", fail_dict)
        report = inspect_pdf_sheet_set([source])
        page, = report["detail_evidence_graph"]["pages"]
        assert page["status"] == "BLOCKED"
        assert "BLOCKED_DECLARATION_EXTRACTION" in page["source_errors"]
        assert report["sheet_detail_inventory"]["region_status_counts"] == {"BLOCKED": 16}
    monkeypatch.setattr(evidence, "_LOCAL_LINK_PAIR_LIMIT", 1)
    value = graph([source])
    assert len(of(value["issues"], "reason_code", "LOCAL_LINK_SEARCH_BUDGET")) == 1
    assert not any(item.get("printed_scale") for item in value["nodes"])
    assert value["topology_pages"][0]["source_operators_accounted_for"]


def test_missing_or_duplicate_evidence_page_does_not_publish_graph(tmp_path, monkeypatch):
    import core.drawings.pdf_auto_intake as intake

    with pytest.raises(ValueError, match="existing PDF"):
        graph([tmp_path / "missing.pdf"])
    source = details(tmp_path)
    build = intake.build_pdf_detail_evidence_graph
    for modify in (lambda pages: pages[:-1], lambda pages: pages + [pages[0]]):
        with monkeypatch.context() as patch:
            patch.setattr(intake, "build_pdf_detail_evidence_graph",
                          lambda report, pages, **options: build(report, modify(pages), **options))
            with pytest.raises(ValueError, match="evidence page"):
                graph([source])
