import pytest

from core.revision import RevisionEngine


def snapshot(total=1000):
    return {
        "drawing": [
            {"source_id": "L1", "length": 10.0},
            {"source_id": "L2", "length": 5.0},
        ],
        "elements": [
            {"element_id": "B1", "kind": "beam", "quantity": 10.0},
        ],
        "takeoff": [
            {"element_id": "B1", "quantity": 10.0, "effective_quantity": 11.0},
        ],
        "boq": [
            {"price_code": "A01", "description": "concrete", "quantity": 11.0,
             "effective_quantity": 11.0, "total": total},
        ],
        "estimate": {
            "cost": {"grand_total": total},
            "factors": {"overhead": 0.10},
        },
    }


def test_revision_detects_drawing_element_quantity_boq_and_cost_changes():
    old = snapshot()
    new = snapshot(1250)
    new["drawing"][0]["length"] = 12.0
    new["elements"][0]["quantity"] = 12.0
    new["takeoff"][0]["quantity"] = 12.0
    new["takeoff"][0]["effective_quantity"] = 13.2
    new["boq"][0]["quantity"] = 13.2
    new["boq"][0]["effective_quantity"] = 13.2

    result = RevisionEngine().compare(old, new, revision_id="R2").as_dict()

    assert result["revision_id"] == "R2"
    assert result["drawing"]["counts"]["changed"] == 1
    assert result["elements"]["counts"]["changed"] == 1
    assert result["takeoff"]["changed"][0]["quantity_changes"][0]["delta"] == pytest.approx(2.0)
    assert result["boq"]["changed"][0]["quantity_changes"][0]["delta"] == pytest.approx(2.2)
    assert result["estimate"]["delta"] == pytest.approx(250)
    assert result["impact"]["affected"] is True
    assert result["impact"]["cost_delta"] == pytest.approx(250)


def test_revision_detects_additions_and_removals_without_mutation():
    old = snapshot()
    new = snapshot()
    del new["drawing"][1]
    new["drawing"].append({"source_id": "L3", "length": 7.0})

    result = RevisionEngine().compare(old, new)
    assert result.drawing["counts"]["added"] == 1
    assert result.drawing["counts"]["removed"] == 1
    assert old["drawing"][1]["source_id"] == "L2"


def test_revision_rejects_invalid_snapshot_or_revision_id():
    with pytest.raises(TypeError):
        RevisionEngine().compare([], snapshot())
    with pytest.raises(ValueError):
        RevisionEngine().compare(snapshot(), snapshot(), revision_id=" ")


def test_revision_fails_closed_on_non_finite_numeric_values():
    old = snapshot()
    new = snapshot()
    new["boq"][0]["quantity"] = float("nan")
    with pytest.raises(ValueError):
        RevisionEngine().compare(old, new)
