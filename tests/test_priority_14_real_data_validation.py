from core.validation.real_data import (
    validate_project,
    validate_takeoffs,
    validate_boq,
    validate_finance,
    validate_drawing_candidates,
)


def test_priority_14_valid_project_is_green():
    project = {
        "id": "P-1",
        "name": "پروژه آزمایشی",
        "takeoffs": [{
            "id": "T1",
            "source_id": "pdf:p1:wall1",
            "description": "دیوار",
            "quantities": [{"amount": 12.5, "unit": "m"}],
        }],
        "boq": [{
            "price_code": "W001",
            "description": "دیوار",
            "quantity": 12.5,
            "unit": "m",
            "source": "pdf:p1:wall1",
            "unit_price": 100,
        }],
        "estimate": {"cost": {"base": 1250}},
        "commitment_entries": [{"id": 1, "amount": 500, "paid_amount": 100}],
        "cost_entries": [{"id": 1, "amount": 200}],
        "receipt_entries": [{"id": 1, "amount": 800}],
        "financial_documents": [{
            "id": 1, "document_number": "INV-1", "amount": 200,
            "cost_entry_id": 1,
        }],
    }
    result = validate_project(project)
    assert result["valid"] is True
    assert result["counts"] == {"errors": 0, "warnings": 0}
    assert result["score"] == 100


def test_priority_14_duplicate_takeoff_source_is_error():
    project = {
        "id": "P-1",
        "name": "P",
        "takeoffs": [
            {"id": "T1", "source_id": "same", "description": "A", "quantities": [{"amount": 1, "unit": "m"}]},
            {"id": "T2", "source_id": "same", "description": "B", "quantities": [{"amount": 2, "unit": "m"}]},
        ],
        "boq": [],
    }
    result = validate_project(project)
    assert result["valid"] is False
    assert any(x["code"] == "duplicate_source" for x in result["issues"])


def test_priority_14_invalid_quantity_unit_and_broken_reference():
    project = {
        "id": "P-1",
        "name": "P",
        "takeoffs": [{
            "id": "T1", "source_id": "s1", "description": "A",
            "quantities": [{"amount": -2, "unit": "madeup"}],
        }],
        "boq": [],
        "commitment_entries": [],
        "cost_entries": [],
        "receipt_entries": [],
        "financial_documents": [{"id": 1, "document_number": "D1", "amount": 1, "cost_entry_id": 99}],
    }
    result = validate_project(project)
    assert result["valid"] is False
    codes = {x["code"] for x in result["issues"]}
    assert {"negative_quantity", "unknown_unit", "broken_reference"} <= codes


def test_priority_14_boq_orphan_source_is_warning_not_error():
    issues = validate_boq([{
        "description": "بتن", "quantity": 3, "unit": "m3",
        "source": "missing-source",
    }], {"known-source"})
    assert any(x.code == "orphan_source" and x.severity == "warning" for x in issues)
    assert not any(x.severity == "error" for x in issues)


def test_priority_14_drawing_candidate_duplicates():
    issues = validate_drawing_candidates({
        "candidates": [
            {"source": "layer:A", "description": "A", "quantity": 1, "unit": "m"},
            {"source": "layer:A", "description": "A2", "quantity": 2, "unit": "m"},
        ]
    })
    assert any(x.code == "duplicate_drawing_source" for x in issues)
