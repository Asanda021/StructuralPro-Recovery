"""Product-level acceptance for the existing StructuralPro workflow.

This gate intentionally composes existing services; it does not introduce a
new application module or duplicate business logic.
"""

from core.aec.disciplines import all_disciplines, takeoff_domain
from core.platform.application import StructuralProApp
from core.pricing.catalog import PriceCatalog, PriceItem
from core.takeoff.estimate import build_estimate


def test_existing_product_workflow_project_to_report_and_persistence(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("پروژه پذیرش", "acceptance-001")

    # Project -> Drawing/Takeoff/Items: use the existing deterministic takeoff service.
    catalog = PriceCatalog([
        PriceItem(1404, "ابنیه", "فصل 1", "W001", "دیوار", "m", 1000),
    ])
    price = catalog.get("W001", 1404).unit_price
    row = app.add_takeoff(
        "acceptance-001",
        "architecture",
        "wall",
        length=5,
        width=0,
        height=3,
        member_code="wall",
        price_code="W001",
        unit_price=price,
        source_id="acceptance-plan-01",
    )
    assert row["quantities"][0]["amount"] == 15
    assert row["quantities"][0]["price_code"] == "W001"

    # Pricebook -> Factors -> BOQ -> Estimate: reuse the production estimate path.
    project = app.open_project("acceptance-001")
    assert len(project["boq"]) == 1
    assert project["boq"][0]["price_code"] == "W001"
    assert project["boq"][0]["quantity"] == 15
    estimate = app.recalculate_estimate("acceptance-001", factors={"بالاسری": 0.10})
    assert estimate["finalizable"] is True
    assert estimate["cost"]["grand_total"] == 16500.0
    assert estimate["factors"]["بالاسری"] == 0.10

    # Estimate -> Statement: persist one period through the existing service.
    period = app.save_statement_period(
        "acceptance-001",
        period_no=1,
        current_quantities={"W001": 2},
        retention_rate=0.10,
    )
    assert period["number"] == 1
    assert period["lines"][0]["current_quantity"] == 2
    assert period["gross_current"] == 2000.0
    assert period["retention"] == 200.0

    statement = app.build_statement(
        "acceptance-001",
        retention_rate=0.10,
    )
    assert statement["lines"][0]["current_quantity"] == 0
    assert statement["payable_current"] == 0.0

    # Statement -> Reports: use the existing project report/export contract.
    report_path = tmp_path / "acceptance.csv"
    result = app.report("acceptance-001", "csv", report_path, period_no=1)
    assert report_path.exists()
    assert result is not None

    # Persistence acceptance: reopen through a new application service instance.
    reopened = StructuralProApp(tmp_path / "data")
    persisted = reopened.open_project("acceptance-001")
    assert persisted is not None
    assert persisted["name"] == "پروژه پذیرش"
    assert len(persisted["takeoffs"]) == 1
    assert len(persisted["boq"]) == 1
    assert len(persisted["statement_periods"]) == 1
    assert persisted["statement_periods"][0]["number"] == 1

    reliability = reopened.project_reliability_status("acceptance-001")
    assert reliability["integrity"]["ok"] is True
    assert reliability["recoverable"] is True


def test_product_workflow_acceptance_has_full_aec_discipline_registry():
    keys = {d.key for d in all_disciplines()}
    required = {
        "architecture",
        "structural_concrete",
        "structural_steel",
        "masonry",
        "timber",
        "composite",
        "mechanical",
        "electrical",
        "renovation",
        "historic",
        "site_external",
    }
    assert required <= keys


def test_product_workflow_estimate_is_fail_closed_for_invalid_factor():
    try:
        build_estimate(
            [{"description": "دیوار", "quantity": 1, "unit": "m", "price_code": "W001", "unit_price": 1000}],
            factors={"بالاسری": -0.10},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("negative engineering/commercial factor must fail closed")
