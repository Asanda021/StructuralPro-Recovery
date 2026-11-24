"""Regression fixtures with invented coordinates for a printed dimension witness."""
from collections import Counter
from hashlib import sha256

import pytest

pymupdf = pytest.importorskip("pymupdf")

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from core.drawings.pdf_component_boundaries import build_pdf_component_boundary_page
from core.drawings.pdf_detail_topology import scan_detail_topology


def _dimension(page, *, vertical=False, variant=None):
    def point(along, across):
        return (across, along) if vertical else (along, across)

    def extension(along, start=144, end=176):
        page.draw_line(point(along, start), point(along, end))

    def arrow(base, tip):
        corners = [point(base, 158.4), point(base, 161.6), point(tip, 160)]
        shape = page.new_shape()
        shape.draw_polyline([*corners, corners[0]])
        outline_only = variant == "outline_only"
        shape.finish(color=(0, 0, 0) if outline_only else None, fill=None if outline_only else (0, 0, 0),
                     closePath=False)
        shape.commit()

    extension(80)
    if variant != "one_extension":
        extension(220)
    if variant == "coincident_extensions":
        extension(220)
    if variant == "competing_extensions":
        extension(80, 140, 180)
        extension(220, 140, 180)
    end = 207 if variant == "misses_base" else 210
    page.draw_line(point(90, 160), point(end, 160))
    if variant == "interrupted_paint":
        page.insert_text((100, 134), "DETAIL AT GRID C")
    arrow(90, 80)
    arrow(210, 200 if variant == "same_direction" else 220)


def _inspect(tmp_path, *, vertical=False, variant=None):
    path = tmp_path / "synthetic-dimension.pdf"
    with pymupdf.open() as document:
        _dimension(document.new_page(width=390, height=310), vertical=vertical, variant=variant)
        document.save(path)
    return inspect_pdf_sheet_set([path]), sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("vertical,variant", [(False, None), (True, None), (False, "coincident_extensions")])
def test_paired_heads_are_annotation_custody_only(tmp_path, vertical, variant):
    report, digest = _inspect(tmp_path, vertical=vertical, variant=variant)
    boundary = report["operator_component_review"]
    rows = boundary["boundary_components"]
    [heads] = [row for row in rows if row["boundary_role"] == "DIMENSION_ARROWHEADS"]
    witness = heads["role_witness"]
    assert heads["classification_status"] == "NON_MEMBER"
    assert heads["reason_code"] == "SOURCE_PAIRED_DIMENSION_ARROWHEADS"
    assert witness["method"] == "VECTOR_DIMENSION_ARROW_PAIR" and witness["source_sha256"] == digest
    assert len(heads["source_operator_ids"]) == 6
    support = set(witness["context_source_operator_ids"])
    assert len(support) == (4 if variant else 3)
    assert not support.intersection(heads["source_operator_ids"])
    assert support.issubset({ref for row in rows if row is not heads for ref in row["source_operator_ids"]})
    assert all(row["physical_member_count"] is None and row["quantity_approval_count"] == 0
               and row["financially_payable"] is False for row in rows)
    accounted = Counter(ref for row in rows for ref in row["source_operator_ids"])
    originals = {op["source_id"] for page in report["detail_evidence_graph"]["topology_pages"]
                 for group in page["groups"] for op in group["source_operators"]}
    assert accounted.keys() == originals and set(accounted.values()) == {1}
    link = next(row for row in boundary["component_source_links"] if row["component_id"] == heads["component_id"])
    assert link["status"] == "EXCLUDED_NON_MEMBER" and link["role_witness"] == witness
    assert link["financially_payable"] is False and report["quantity_approval_count"] == 0


@pytest.mark.parametrize("variant", ["one_extension", "same_direction", "misses_base", "interrupted_paint",
                                    "competing_extensions", "outline_only"])
def test_isolated_or_competing_ink_cannot_establish_dimension_heads(tmp_path, variant):
    report, _ = _inspect(tmp_path, variant=variant)
    review = report["operator_component_review"]
    assert all(row["boundary_role"] != "DIMENSION_ARROWHEADS" for row in review["boundary_components"])
    assert all(row["status"] not in {"PROPOSED", "REVIEW_BACKED"} for row in review["component_source_links"])


def test_arrow_witness_budget_blocks_without_discarding_ink():
    with pymupdf.open() as document:
        page = document.new_page(width=390, height=310)
        _dimension(page, variant="coincident_extensions")
        paths = page.get_drawings()
        topology = scan_detail_topology(page, document_id="D", page_number=1, paths=paths)
    rows, receipt = build_pdf_component_boundary_page(
        topology, document_id="D", page=1, digest="a" * 64, sheet_kind="unknown",
        path_groups={}, paint_sequences=[draw["seqno"] for draw in paths], max_enclosure_checks=1,
    )
    assert receipt["status"] == "BLOCKED"
    assert receipt["reason_code"] == "BLOCKED_DIMENSION_WITNESS_BUDGET"
    assert {row["classification_status"] for row in rows} == {"BLOCKED"}
    assert receipt["accounted_operator_count"] == sum(len(draw["items"]) for draw in paths)


@pytest.mark.parametrize("source_damage", ["lost", "duplicate"])
def test_arrow_witness_requires_an_intact_operator_manifest(source_damage):
    with pymupdf.open() as document:
        page = document.new_page(width=390, height=310)
        _dimension(page)
        paths = page.get_drawings()
        topology = scan_detail_topology(page, document_id="D", page_number=1, paths=paths)
    arrows = next(group["source_operators"] for group in topology["groups"]
                  if any(op["paint"] == "f" for op in group["source_operators"]))
    head_index = next(index for index, op in enumerate(arrows) if op["paint"] == "f")
    kwargs = {"document_id": "D", "page": 1, "digest": "a" * 64, "sheet_kind": "unknown", "path_groups": {},
              "paint_sequences": [draw["seqno"] for draw in paths]}
    if source_damage == "duplicate":
        arrows.append(arrows[head_index])
        with pytest.raises(ValueError, match="duplicate boundary source operator"):
            build_pdf_component_boundary_page(topology, **kwargs)
    else:
        arrows.pop(head_index)
        rows, receipt = build_pdf_component_boundary_page(topology, **kwargs)
        assert receipt["status"] == "BLOCKED" and receipt["unaccounted_operator_count"] == 1
        assert {row["classification_status"] for row in rows} == {"BLOCKED"}


@pytest.mark.parametrize("case, expected_pairs", [
    ("chain", 2), ("isolated", 0), ("competing_extensions", 0), ("fork", 0),
])
def test_one_sided_extensions_require_corroborating_dimension_chain(tmp_path, case, expected_pairs):
    path = tmp_path / "synthetic-chain.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=310)
        for x in (65, 185, 325):
            page.draw_line((x, 130), (x, 195))
            if case == "competing_extensions":
                page.draw_line((x, 130), (x, 180))
        intervals = [(65, 185)] if case == "isolated" else [(65, 185), (185, 325)]
        if case == "fork":
            page.draw_line((185, 130), (185, 180))
            page.draw_line((375, 130), (375, 180))
            intervals.append((185, 375))
        for left, right in intervals:
            page.draw_line((left + 10, 130), (right - 10, 130))
            for tip, base in ((left, left + 10), (right, right - 10)):
                shape = page.new_shape()
                shape.draw_polyline([(base, 128), (base, 132), (tip, 130), (base, 128)])
                shape.finish(color=None, fill=(0, 0, 0), closePath=False)
                shape.commit()
        doc.save(path)

    report = inspect_pdf_sheet_set([path])
    rows = report["operator_component_review"]["boundary_components"]
    heads = [row for row in rows if row["boundary_role"] == "DIMENSION_ARROWHEADS"]
    assert len(heads) == expected_pairs
    assert all(len(row["source_operator_ids"]) == 6 and row["classification_status"] == "NON_MEMBER"
               and not row["financially_payable"] for row in heads)
    if heads:
        first, second = heads
        for row, neighbor in ((first, second), (second, first)):
            support = set(row["role_witness"]["context_source_operator_ids"])
            assert set(neighbor["source_operator_ids"]) <= support
            assert not support.intersection(row["source_operator_ids"])
    apportioned = Counter(ref for row in rows for ref in row["source_operator_ids"])
    originals = {op["source_id"] for topology in report["detail_evidence_graph"]["topology_pages"]
                 for group in topology["groups"] for op in group["source_operators"]}
    assert apportioned == Counter(originals)
