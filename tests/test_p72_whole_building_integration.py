import pytest
from core.takeoff.generic import measure
from core.project.domains import normalize_discipline

def test_generic_measurement_supports_all_core_building_disciplines():
    for raw in ("معماری", "سازه", "بتن", "فولاد", "بنایی", "مکانیک", "برق", "عمران"):
        discipline = normalize_discipline(raw)
        row = measure(discipline, "area", length=10, width=2)
        assert row.discipline == discipline
        assert row.quantity == pytest.approx(20)
        assert row.unit == "m2"

def test_generic_volume_and_count_are_deterministic():
    assert measure("steel", "volume", length=2, width=3, height=4).quantity == 24
    assert measure("electrical", "count", count=12).quantity == 12

def test_generic_measurement_rejects_invalid_values():
    with pytest.raises(ValueError):
        measure("architecture", "area", length=-1, width=2)
