"""G2 geometry measurement probe: deterministic synthetic unit checks.

These are not evidence that independently published IFC models render.
"""
from __future__ import annotations

import hashlib
import json

from scripts.diagnostics.p6_independent_ifc_geometry_capacity import (
    analyze_file, percentile,
)
from test_phase6_p2_benchmark_ifc100 import make_ifc_floors


def test_capacity_percentile_uses_nearest_rank_without_interpolating():
    assert percentile([], 50) == 0
    assert percentile([12], 99) == 12
    assert percentile([7, 1, 9, 3, 5], 50) == 5
    assert percentile([7, 1, 9, 3, 5], 90) == 9


def test_meter_counts_original_ifc4_triangles_without_raising_product_limit(tmp_path):
    source = tmp_path / "synthetic-not-client.ifc"
    make_ifc_floors(source, 1)
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    out = tmp_path / "counts.json"
    row = analyze_file(source, expected, out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved == row
    assert row["status"] == "COMPLETE_ALL_MEMBERS_MEASURED"
    assert row["triangle_total_is_complete"] is True
    assert row["source_sha256_verified"] is True
    assert row["source_ifc_elements"] == 4
    assert row["valid_mesh_elements"] == 4
    assert row["processed_elements"] == 4
    assert row["failed_to_tessellate_elements"] == 0
    assert row["triangle_total_measured"] == 48
    assert row["maximum_member_triangles"] == 12
    assert row["product_triangle_limit_unchanged"] == 40000
    assert row["quantity_authority"] is False
    assert "vertices" not in row
    assert "global_id" not in row


def test_meter_rejects_wrong_source_digest_and_stays_incomplete(tmp_path):
    source = tmp_path / "synthetic-rejected.ifc"
    make_ifc_floors(source, 1)
    out = tmp_path / "rejected.json"
    row = analyze_file(source, "0" * 64, out)
    assert row["status"] == "SOURCE_HASH_MISMATCH"
    assert row["source_sha256_verified"] is False
    assert row["triangle_total_is_complete"] is False
    assert row["triangle_total_measured"] == 0
