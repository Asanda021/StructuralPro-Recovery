"""Manufacturer-reviewed void volume, not bounding box, is required for Uboot."""
import pytest
from core.takeoff.modules.building import calculate_building_item
from core.platform.application import StructuralProApp

BASIC={"length":6,"width":6,"thickness":.28,"count":1,"void_count":40}

@pytest.mark.parametrize("extra",[
    {"void_length":.5,"void_width":.25,"void_height":.2},
    {"void_volume":.02},
    {"void_volume":.02,"void_spec_ref":"  "},
])
def test_uboot_blocked_without_manufacturer_void_origin(extra):
    with pytest.raises(ValueError,match="void_volume and void_spec_ref"):
        calculate_building_item("uboot_roof",**BASIC,**extra)


def test_uboot_reviewed_void_volume_preserves_reference():
    r=calculate_building_item("uboot_roof",**BASIC,void_volume=.02,void_spec_ref="synthetic:manufacturer:sheet1")
    assert r.quantity==pytest.approx(9.28)
    assert r.unit=="m3"


def test_uboot_no_boq_on_missing_verified_void(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("آزمایش سقف مجوف","P")
    before=app.open_project("P")
    with pytest.raises(ValueError):
        app.add_takeoff("P","building","uboot_roof",source_id="synthetic:roof:U1",**BASIC,
                        void_length=.5,void_width=.25,void_height=.2)
    assert app.open_project("P")==before
    app.store.close()
