"""P8P2 source-backed dual-reference calibration tests (synthetic data only).

No private user drawing, PDF, or font is stored in this repository.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import fitz
import pytest

from core.drawings.dwg_takeoff import DWGDocument, DWGEntity, apply_documented_units


def _evidence(tmp_path):
    drawing = tmp_path / "synthetic_original.dwg"
    drawing.write_bytes(b"AC1018_SYNTHETIC_ONLY_NOT_A_REAL_DWG")
    drawing_sha = sha256(drawing.read_bytes()).hexdigest()
    pdf = tmp_path / "synthetic_matching_sheet.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 40), "SYNTHETIC PROJECT P1 REV A MEMBER M1 = 2 m")
        page.insert_text((40, 60), "SYNTHETIC PROJECT P1 REV A MEMBER M2 = 3.5 m")
        document.save(pdf)
    document = DWGDocument(
        source=str(drawing), source_sha256=drawing_sha,
        format="DWG->DXF (test)", units="unitless",
        entities=[
            DWGEntity("LINE", "WALL", "AB1", {
                "start": (0.0, 0.0), "end": (2000.0, 0.0),
                "length": 2000.0, "layer_visible": True, "layer_defined": True,
            }),
            DWGEntity("LINE", "WALL", "AB2", {
                "start": (0.0, 20.0), "end": (0.0, 3520.0),
                "length": 3500.0, "layer_visible": True, "layer_defined": True,
            }),
        ],
    )
    proof = {
        "policy": "cad_unit_reference_v2",
        "source_sha256": drawing_sha,
        "source_pdf_path": str(pdf),
        "source_pdf_sha256": sha256(pdf.read_bytes()).hexdigest(),
        "project_id": "SYNTHETIC-P1",
        "pdf_project_id": "SYNTHETIC-P1",
        "drawing_revision": "A",
        "pdf_drawing_revision": "A",
        "unit": "mm",
        "absolute_tolerance_m": "0.00001",
        "author": "draft_author",
        "reviewer": "independent_reviewer",
        "reference": "Explicit drawing revision and two independently documented lines",
        "references": [
            {"reference_handle": "AB1", "member_id": "M1", "sheet_id": "S1",
             "pdf_page": 1, "cad_length": "2000", "real_length_m": "2"},
            {"reference_handle": "AB2", "member_id": "M2", "sheet_id": "S1",
             "pdf_page": 1, "cad_length": "3500", "real_length_m": "3.5"},
        ],
    }
    return document, proof, pdf


def _apply(tmp_path, document, proof):
    receipt = tmp_path / "unit_proof_v2.json"
    receipt.write_text(json.dumps(proof), encoding="utf-8")
    return apply_documented_units(document, {
        "path": str(receipt), "sha256": sha256(receipt.read_bytes()).hexdigest(),
    })


def test_two_independent_pdf_source_linked_lines_change_only_copy(tmp_path):
    doc, proof, _ = _evidence(tmp_path)
    reviewed = _apply(tmp_path, doc, proof)
    assert reviewed.units == "mm"
    assert [e.data["length"] for e in reviewed.entities] == pytest.approx([2.0, 3.5])
    assert reviewed.entities[1].data["start"] == pytest.approx((0.0, 0.02))
    assert doc.units == "unitless"
    assert doc.entities[0].data["length"] == 2000.0


@pytest.mark.parametrize("change", [
    "one_reference", "duplicate_handle", "duplicate_member", "same_geometry",
    "wrong_length", "wrong_real_length", "wrong_project",
    "unknown_revision", "bad_pdf_sha", "bad_source_sha",
    "bad_page", "bad_tolerance", "missing_review",
])
def test_fail_closed_if_two_source_references_not_proven(tmp_path, change):
    doc, proof, _ = _evidence(tmp_path)
    if change == "one_reference":
        proof["references"].pop()
    elif change == "duplicate_handle":
        proof["references"][1]["reference_handle"] = "AB1"
    elif change == "duplicate_member":
        proof["references"][1]["member_id"] = "M1"
    elif change == "same_geometry":
        entities = list(doc.entities)
        second = dict(entities[1].data, start=(0.0, 0.0), end=(2000.0, 0.0), length=2000.0)
        doc.entities[1] = DWGEntity("LINE", "WALL", "AB2", second)
        proof["references"][1]["cad_length"] = "2000"
        proof["references"][1]["real_length_m"] = "2"
    elif change == "wrong_length":
        proof["references"][1]["cad_length"] = "5000"
    elif change == "wrong_real_length":
        proof["references"][1]["real_length_m"] = "3"
    elif change == "wrong_project":
        proof["pdf_project_id"] = "ANOTHER-PROJECT"
    elif change == "unknown_revision":
        proof["drawing_revision"] = "UNKNOWN"
        proof["pdf_drawing_revision"] = "UNKNOWN"
    elif change == "bad_pdf_sha":
        proof["source_pdf_sha256"] = "0" * 64
    elif change == "bad_source_sha":
        proof["source_sha256"] = "0" * 64
    elif change == "bad_page":
        proof["references"][0]["pdf_page"] = 100
    elif change == "bad_tolerance":
        proof["absolute_tolerance_m"] = "0.1"
    elif change == "missing_review":
        proof["reviewer"] = proof["author"]
    with pytest.raises(ValueError):
        _apply(tmp_path, doc, proof)
    assert doc.units == "unitless"


def test_legacy_one_reference_cannot_calibrate_real_dwg_source(tmp_path):
    doc, proof, _ = _evidence(tmp_path)
    legacy = {
        "policy": "cad_unit_reference_v1",
        "source_sha256": doc.source_sha256,
        "unit": "mm",
        "reference_handle": "AB1",
        "cad_length": "2000",
        "real_length_m": "2",
        "author": "draft_author",
        "reviewer": "independent_reviewer",
        "reference": "SYNTHETIC",
    }
    with pytest.raises(ValueError, match="v2"):
        _apply(tmp_path, doc, legacy)
    assert doc.units == "unitless"
