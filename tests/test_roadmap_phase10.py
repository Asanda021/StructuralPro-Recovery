import pytest

from core.platform.application import StructuralProApp
from core.takeoff.estimate import build_estimate


def test_phase10_takeoff_to_boq_estimate_statement_and_report(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("پروژه آزمون فاز ۱۰", "phase10-001")
    row = app.add_takeoff(
        "phase10-001",
        "architecture",
        "wall",
        length=5,
        width=0,
        height=3,
        member_code="wall",
        price_code="W001",
        unit_price=1000,
        source_id="drawing:A:01",
    )
    assert row["source_id"] == "drawing:A:01"
    assert row["quantities"][0]["amount"] == pytest.approx(15)

    project = app.open_project("phase10-001")
    assert len(project["boq"]) == 1
    assert project["boq"][0]["price_code"] == "W001"
    assert project["boq"][0]["quantity"] == pytest.approx(15)
    assert project["boq"][0]["source_id"] == "drawing:A:01"

    estimate = app.recalculate_estimate("phase10-001", factors={"بالاسری": 0.10})
    assert estimate["finalizable"] is True
    assert estimate["cost"]["base"] == pytest.approx(15000)
    assert estimate["cost"]["grand_total"] == pytest.approx(16500)

    period = app.save_statement_period(
        "phase10-001",
        period_no=1,
        current_quantities={"W001": 2},
        retention_rate=0.10,
    )
    assert period["number"] == 1
    assert period["gross_current"] == pytest.approx(2000)
    assert period["retention"] == pytest.approx(200)

    output = tmp_path / "phase10.csv"
    result = app.report("phase10-001", "csv", output, period_no=1)
    assert output.exists()
    assert output.stat().st_size > 0
    assert result is not None


def test_phase10_estimate_rejects_negative_factors():
    with pytest.raises(ValueError):
        build_estimate(
            [{"description": "دیوار", "quantity": 1, "unit": "m", "price_code": "W001", "unit_price": 1000}],
            factors={"بالاسری": -0.10},
        )
