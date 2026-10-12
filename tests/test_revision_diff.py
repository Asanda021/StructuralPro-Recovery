from core.drawings.revision_diff import compare_revisions, summarize_revision


def test_revision_diff_detects_added_removed_and_quantity_change():
    before = [
        {"source": "cad:WALL:A1", "quantity": 10, "unit": "m", "description": "WALL"},
        {"source": "cad:COL:C1", "quantity": 2, "unit": "عدد", "description": "COLUMN"},
    ]
    after = [
        {"source": "cad:WALL:A1", "quantity": 12.5, "unit": "m", "description": "WALL"},
        {"source": "cad:DOOR:D1", "quantity": 1, "unit": "عدد", "description": "DOOR"},
    ]
    changes = compare_revisions(before, after)
    by_key = {row["key"]: row for row in changes}
    assert by_key["cad:WALL:A1"]["change_type"] == "changed"
    assert by_key["cad:WALL:A1"]["quantity_delta"] == 2.5
    assert by_key["cad:COL:C1"]["change_type"] == "removed"
    assert by_key["cad:DOOR:D1"]["change_type"] == "added"


def test_revision_diff_detects_metadata_change_without_quantity_change():
    before = [{"source": "cad:A1", "quantity": 5, "unit": "m", "description": "OLD"}]
    after = [{"source": "cad:A1", "quantity": 5, "unit": "m", "description": "NEW"}]
    changes = compare_revisions(before, after)
    assert changes[0]["change_type"] == "changed"
    assert changes[0]["quantity_delta"] == 0


def test_revision_diff_respects_quantity_tolerance():
    before = [{"source": "cad:A1", "quantity": 5, "unit": "m"}]
    after = [{"source": "cad:A1", "quantity": 5.0000000001, "unit": "m"}]
    changes = compare_revisions(before, after)
    assert changes[0]["change_type"] == "unchanged"


def test_revision_summary_counts_changes():
    changes = [
        {"change_type": "added"}, {"change_type": "removed"},
        {"change_type": "changed"}, {"change_type": "unchanged"},
        {"change_type": "changed"},
    ]
    assert summarize_revision(changes) == {
        "added": 1, "removed": 1, "changed": 2, "unchanged": 1,
    }


def test_revision_diff_rejects_invalid_tolerance():
    import math
    before = [{"source": "cad:A1", "quantity": 1}]
    after = [{"source": "cad:A1", "quantity": 1}]
    for tolerance in (-1, math.nan, math.inf):
        try:
            compare_revisions(before, after, quantity_tolerance=tolerance)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid tolerance must be rejected")
