"""Synthetic-only regression for BLOCK reference evidence. No private CAD."""
from __future__ import annotations

import ezdxf
import pytest

from core.drawings.dwg_block_references import audit_raw_dxf_block_references


def _drawing(tmp_path, *, direct=False, nested=False):
    doc = ezdxf.new("R2018")
    target = doc.blocks.new("*U_TARGET")
    target.add_line((0, 0, 0), (1, 0, 0))
    if direct:
        doc.modelspace().add_blockref("*U_TARGET", (2, 3))
    if nested:
        parent = doc.blocks.new("PARENT")
        parent.add_blockref("*U_TARGET", (1, 1))
        doc.modelspace().add_blockref("PARENT", (4, 4))
    path = tmp_path / "synthetic-blocks.dxf"
    doc.saveas(path)
    return path, str(target.block_record_handle)


def test_unreferenced_definition_is_not_approved_or_claimed_unused(tmp_path):
    path, record = _drawing(tmp_path)
    audit = audit_raw_dxf_block_references(path, record)
    assert audit["status"] == "RAW_DXF_NO_OBSERVED_BLOCK_REFERENCE_NOT_PROOF_UNUSED"
    assert audit["target_block_definition_count"] == 1
    assert audit["observed_raw_insert_count"] == 0
    assert audit["observed_direct_target_references"] == 0
    assert audit["observed_reachable_target"] is False
    assert audit["complete_original_dwg_reference_coverage_verified"] is False
    assert audit["financial_quantity_approved"] is False


def test_direct_modelspace_insert_is_detected(tmp_path):
    path, record = _drawing(tmp_path, direct=True)
    audit = audit_raw_dxf_block_references(path, record)
    assert audit["status"] == "RAW_DXF_OBSERVED_REFERENCED_BLOCK"
    assert audit["observed_raw_insert_count"] == 1
    assert audit["observed_direct_target_references"] == 1
    assert audit["observed_reachable_target"] is True
    assert audit["financial_quantity_approved"] is False


def test_reachable_nested_insert_is_detected_without_false_direct_reference(tmp_path):
    path, record = _drawing(tmp_path, nested=True)
    audit = audit_raw_dxf_block_references(path, record)
    assert audit["status"] == "RAW_DXF_OBSERVED_REFERENCED_BLOCK"
    assert audit["observed_raw_insert_count"] == 2
    assert audit["observed_direct_target_references"] == 0
    assert audit["observed_any_target_references"] == 1
    assert audit["observed_reachable_target"] is True


def test_unreachable_nested_reference_is_not_described_as_used(tmp_path):
    doc = ezdxf.new("R2018")
    target = doc.blocks.new("*U_TARGET")
    target.add_line((0, 0), (1, 1))
    orphan = doc.blocks.new("ORPHAN")
    orphan.add_blockref("*U_TARGET", (0, 0))
    path = tmp_path / "unreachable.dxf"
    doc.saveas(path)
    audit = audit_raw_dxf_block_references(path, target.block_record_handle)
    assert audit["observed_raw_insert_count"] == 1
    assert audit["observed_any_target_references"] == 1
    assert audit["observed_reachable_target"] is False
    assert audit["status"] == "RAW_DXF_NO_OBSERVED_BLOCK_REFERENCE_NOT_PROOF_UNUSED"
    assert audit["financial_quantity_approved"] is False


def test_invalid_record_handle_is_rejected(tmp_path):
    path, _ = _drawing(tmp_path)
    with pytest.raises(ValueError, match="hexadecimal"):
        audit_raw_dxf_block_references(path, "THIS_IS_NOT_HEX")
