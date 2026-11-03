"""Synthetic-only regression: an explicit decoder financial veto must be enforced.

No private drawing or takeoff data; an absent flag is not proof of release
acceptance and never bypasses the existing independent CAD review gates.
"""
from types import SimpleNamespace

import pytest

from core.drawings.dwg_takeoff import (
    DWGDocument, DWGEntity, DWGTakeoffEngine, cad_entity_geometry, verify_cad_item,
)


def _document(*, forbidden: bool) -> DWGDocument:
    conversion = {
        "provider": "synthetic strict recovery",
        "decoder_version": "synthetic-only",
    }
    if forbidden:
        conversion["geometry_approved_for_financial_takeoff"] = False
    return DWGDocument(
        format="DWG→DXF (strict recovered missing LINEs)" if forbidden else "DXF",
        units="m",
        conversion=conversion,
        entities=[
            DWGEntity("LINE", "synthetic", "F00", {
                "start": (0.0, 0.0),
                "end": (3.0, 4.0),
                "length": 5.0,
                "layer_visible": True,
                "layer_defined": True,
            }),
        ],
    )


def test_explicit_false_blocks_entity_geometry_even_with_valid_units():
    doc = _document(forbidden=True)
    with pytest.raises(ValueError, match="متره مالی رد شده"):
        cad_entity_geometry(doc, "F00", "length")


def test_explicit_false_blocks_layer_takeoff_count_and_length():
    doc = _document(forbidden=True)
    for metric in ("count", "length"):
        with pytest.raises(ValueError, match="متره مالی رد شده"):
            DWGTakeoffEngine().layer_takeoff(doc, {
                "synthetic": {"metric": metric},
            })


def test_explicit_false_blocks_review_even_when_independent_review_not_required():
    doc = _document(forbidden=True)
    fake_item = SimpleNamespace(cad_evidence=None)
    with pytest.raises(ValueError, match="متره مالی رد شده"):
        verify_cad_item(fake_item, doc, require_review=False)


def test_missing_flag_is_not_new_auto_approval_or_blanket_rejection():
    doc = _document(forbidden=False)
    e, points, length = cad_entity_geometry(doc, "F00", "length")
    assert e.handle == "F00"
    assert points == [(0.0, 0.0), (3.0, -4.0)]
    assert length == 5.0
    # Layer summaries remain explicitly review-required.
    rows = DWGTakeoffEngine().layer_takeoff(doc, {
        "synthetic": {"metric": "length"},
    })
    assert len(rows) == 1
    assert rows[0]["needs_confirmation"] is True
