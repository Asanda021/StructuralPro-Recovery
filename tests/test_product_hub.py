from core.platform.product_hub import ProductHub


def test_product_hub_registers_100_capabilities():
    hub = ProductHub()
    assert len(hub.capabilities()) == 100
    assert hub.summary()["offline_core"] is True
    assert hub.summary()["local_ai"] is True


def test_product_hub_project_qa_and_bulk_operations():
    hub = ProductHub()
    project = {
        "name": "پروژه آزمایشی",
        "takeoffs": [{
            "id": "1",
            "member_code": "F1",
            "quantities": [{
                "code": "C",
                "title": "بتن",
                "unit": "m3",
                "amount": 2,
            }],
        }],
    }
    assert hub.validate_project(project) == []
    changed = hub.apply_bulk(project, {"price_year": 1405})
    assert changed["takeoffs"][0]["price_year"] == 1405
    copied = hub.duplicate_takeoff(project, "F1", 1)
    assert len(copied["takeoffs"]) == 2


def test_product_hub_connects_local_ai_and_dwg_bindings():
    hub = ProductHub()
    ai = hub.get("ai-assistant").handler
    response = ai("هل يعمل آفلاین؟")
    assert response.source == "local-rule-engine"
    assert hub.get("cad-dwg").handler is not None
    assert hub.get("pricing-import").handler is not None
