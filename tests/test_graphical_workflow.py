from core.drawings.graphical_takeoff import ScaleCalibration,Point,MeasurementStore,polygon_area,subtract_areas,snap_point
from core.takeoff.assemblies import AssemblyLibrary
from core.takeoff.workflow import TakeoffWorkflow
from core.ai.auto_takeoff import LocalAutoTakeoff

def test_scale_and_geometry():
    s=ScaleCalibration.parse("1:100",drawing_unit="cm")
    assert round(s.length(2),2)==2
    assert round(s.area(1),2)==1
    pts=[Point(0,0),Point(2,0),Point(2,3),Point(0,3)]
    assert polygon_area(pts)==6
    assert subtract_areas(6,[1,2])==3
    assert snap_point(Point(2.01,2.99),[Point(2,3)],.05)==Point(2,3)

def test_graphical_store():
    s=ScaleCalibration.parse("1:100",drawing_unit="cm")
    m=MeasurementStore()
    a=m.add_length([Point(0,0),Point(2,0)],s,page=1,label="دیوار")
    b=m.add_area([Point(0,0),Point(2,0),Point(2,2),Point(0,2)],s,page=1,label="کف")
    c=m.add_count(4,page=1,label="در")
    assert a.unit=="m" and round(a.value,2)==2
    assert b.unit=="m2" and round(b.value,2)==4
    assert c.value==4
    assert m.summary()["count"]==3

def test_assemblies_are_reusable_and_deterministic():
    lib=AssemblyLibrary()
    x=lib.expand("SLAB-CON",10)
    assert any(i["code"]=="REBAR" and i["quantity"]==120 for i in x)
    assert sum(i["cost"] for i in x)==0

def test_local_auto_takeoff():
    class E:
        layer="WALL"
        entity_type="LINE"
        data={"length":5}
    ai=LocalAutoTakeoff()
    rows=ai.auto_takeoff([E()])
    assert rows[0]["kind"]=="wall" and rows[0]["quantity"]==5
    assert rows[0]["needs_confirmation"] is True
    assert ai.auto_scale("Plan 1:100") == 100

def test_end_to_end_workflow_is_reviewable():
    w=TakeoffWorkflow()
    rows=[{"description":"concrete wall","quantity":10,"unit":"m2","price_code":"A1"}]
    out=w.build_estimate(rows,{"A1":250})
    assert out[0]["total"]==2500
    mapped=w.map_price_codes(rows,[{"code":"A1","description":"concrete wall","group":"building","chapter":"concrete"}])
    assert mapped[0]["price_code"]=="A1"



def test_phase_three_to_five_viewer_zoom_and_persian_cad_are_wired():
    from pathlib import Path
    source = Path("app/graphical_takeoff.py").read_text(encoding="utf-8")
    assert '"نقشه‌ها (*.pdf *.dwg *.dxf *.ifc)' in source
    assert 'self.zoom_window = QPushButton("بزرگ‌نمایی ناحیه")' in source
    assert 'self.select_region = QPushButton("انتخاب ناحیه")' in source
    assert 'self.region_to_takeoff = QPushButton("ثبت ناحیه در متره")' in source
    assert "self.fitInView(scene_rect" in source
    assert "normalize_cad_text(d[\"text\"])" in source
    assert "is_rtl_cad_text(text)" in source
    assert "کالیبراسیون لازم است" in source


def test_drawing_scale_calibration_is_independent_per_page():
    import pytest
    from core.drawings.takeoff_session import DrawingTakeoffSession
    from core.drawings.graphical_takeoff import Point

    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(1, 100, 10)
    first = session.add_length([Point(0, 0), Point(100, 0)], page=1, source="page1-wall")
    assert first.quantity == 10
    session.set_page(2)
    assert session.calibration is None
    with pytest.raises(ValueError, match="صفحه 2"):
        session.add_length([Point(0, 0), Point(100, 0)], page=2, source="page2-wall")
    session.calibrate(2, 100, 5)
    second = session.add_length([Point(0, 0), Point(100, 0)], page=2, source="page2-wall")
    assert second.quantity == 5
    session.set_page(1)
    assert session.calibration is not None and session.calibration.page == 1
    third = session.add_length([Point(0, 0), Point(100, 0)], page=1, source="page1-wall-2")
    assert third.quantity == 10


def test_drawing_calibration_rejects_non_finite_reference_values():
    import math
    import pytest
    from core.drawings.takeoff_session import DrawingTakeoffSession

    session = DrawingTakeoffSession("plan.pdf")
    for pixels, meters in ((math.nan, 10), (math.inf, 10), (100, math.nan), (100, math.inf)):
        with pytest.raises(ValueError, match="finite"):
            session.calibrate(1, pixels, meters)


def test_calibrating_another_page_does_not_change_active_page_scale():
    from core.drawings.takeoff_session import DrawingTakeoffSession

    session = DrawingTakeoffSession("plan.pdf")
    first = session.calibrate(1, 100, 10)
    second = session.calibrate(2, 100, 5)
    assert second.page == 2
    assert session.calibration == first
    session.set_page(2)
    assert session.calibration == second
