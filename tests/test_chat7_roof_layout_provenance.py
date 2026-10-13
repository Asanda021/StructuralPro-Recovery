"""No waffle or hollow-core payable quantity without reviewed physical geometry."""
import pytest
from core.takeoff.modules.building import calculate_building_item
from core.platform.application import StructuralProApp

WAFFLE = dict(length=6,width=6,top_thickness=.06,rib_width=.12,rib_depth=.18,
              rib_count_x=10,rib_count_y=10,intersection_count=100,
              rib_run_length_x_m=6,rib_run_length_y_m=6,
              layout_ref='synthetic:waffle-L1',approved_by='synthetic:reviewer',count=1)
HOLLOW=dict(length=10,width=4,thickness=.2,void_diameter=.1,void_count=20,
            void_cross_section='circular',void_effective_length_m=10,
            void_spec_ref='synthetic:hollow-profile',void_reviewed_by='synthetic:reviewer',count=1)

@pytest.mark.parametrize('field',['rib_count_x','rib_count_y','intersection_count',
                                  'rib_run_length_x_m','rib_run_length_y_m','layout_ref','approved_by'])
def test_waffle_requires_actual_layout_components(field):
    data=dict(WAFFLE);data.pop(field)
    with pytest.raises((ValueError,TypeError)):
        calculate_building_item('waffle_roof',**data)

@pytest.mark.parametrize('field',['void_cross_section','void_effective_length_m',
                                  'void_spec_ref','void_reviewed_by'])
def test_hollow_core_requires_actual_section_review(field):
    data=dict(HOLLOW);data.pop(field)
    with pytest.raises((ValueError,TypeError)):
        calculate_building_item('hollow_core_roof',**data)

@pytest.mark.parametrize('key,value',[('rib_count_x',1.5),('intersection_count',101),
                                      ('rib_run_length_x_m',7),('rib_run_length_y_m',float('nan'))])
def test_invalid_waffle_layout_never_mints_quantity(key,value):
    data=dict(WAFFLE);data[key]=value
    with pytest.raises(ValueError):
        calculate_building_item('waffle_roof',**data)

def test_signed_layout_golden_values_are_not_inferred_from_spacing():
    waffle=calculate_building_item('waffle_roof',**WAFFLE)
    hollow=calculate_building_item('hollow_core_roof',**HOLLOW)
    assert waffle.quantity==pytest.approx(4.4928)
    assert hollow.quantity==pytest.approx(6.429203673205103)
    assert all('spacing' not in key for key in WAFFLE)

def test_unreviewed_roof_does_not_touch_sqlite_or_boq(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project('سقف‌های پیچیده','P')
    before=app.open_project('P')
    with pytest.raises((ValueError,TypeError)):
        app.add_takeoff('P','building','waffle_roof',source_id='synthetic:waffle',
                        length=6,width=6,top_thickness=.06,
                        spacing_x=.6,spacing_y=.6,rib_width=.12,rib_depth=.18,count=1)
    with pytest.raises((ValueError,TypeError)):
        app.add_takeoff('P','building','hollow_core_roof',source_id='synthetic:hollow',
                        length=10,width=4,thickness=.2,void_diameter=.1,void_count=20,count=1)
    assert app.open_project('P')==before
    app.store.close()
