import pytest

from core.takeoff.modules.building import calculate_building_item


def test_stair_takeoff_rejects_box_volume_and_requires_sloped_geometry():
    with pytest.raises(ValueError, match="sloped_length"):
        calculate_building_item("stair_concrete", length=4, width=1.2, thickness=.15, count=1)


def test_stair_takeoff_uses_sloped_waist_geometry():
    r = calculate_building_item(
        "stair_concrete", sloped_length=5.0, width=1.2,
        waist_thickness=.15, count=1,
    )
    assert r.unit == "m3"
    assert r.quantity == pytest.approx(.9)
    assert "دال شیب‌دار" in r.item
