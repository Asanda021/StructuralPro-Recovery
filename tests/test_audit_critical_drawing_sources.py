import pytest
import pymupdf
from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp


def pdf(path,raster=False):
    doc=pymupdf.open();page=doc.new_page(width=200,height=200)
    page.draw_line((10,10),(100,10));page.draw_line((10,20),(100,20))
    if raster:
        image=page.get_pixmap().tobytes('png');doc.close()
        doc=pymupdf.open();page=doc.new_page(width=200,height=200);page.insert_image(page.rect,stream=image)
    doc.save(path);doc.close()


def measure(path,y=10,reverse=False):
    s=DrawingTakeoffSession(str(path));s.calibrate(1,100,10)
    points=[Point(10,y),Point(100,y)]
    if reverse:points.reverse()
    s.add_length(points,page=1,takeoff_code='A',label='طول با شاهد صریح')
    return s


def commit(app,s):
    saved=app.save_drawing_takeoff_session('p',s)
    return app.commit_drawing_takeoff_to_boq('p',saved['session_id'],[s.items[0].id],expected_session_revision=saved['revision'])


def project(tmp_path):
    a=StructuralProApp(tmp_path/'data');a.create_project('منشأ معتبر','p');return a


def test_changed_source_after_measurement_is_rejected(tmp_path):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path);s=measure(path)
    saved=a.save_drawing_takeoff_session('p',s)
    path.write_bytes(b'changed source')
    with pytest.raises(ValueError):a.commit_drawing_takeoff_to_boq('p',saved['session_id'],[s.items[0].id],expected_session_revision=1)
    assert not a.open_project('p')['takeoffs'];a.store.close()


def test_raster_without_vector_evidence_is_rejected(tmp_path):
    path=tmp_path/'raster.pdf';pdf(path,True);a=project(tmp_path)
    with pytest.raises(ValueError):commit(a,measure(path))
    assert not a.open_project('p')['takeoffs'];a.store.close()


@pytest.mark.parametrize('reverse',[False,True])
def test_cross_session_same_measurement_cannot_be_counted_twice(tmp_path,reverse):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path);commit(a,measure(path))
    with pytest.raises(ValueError):commit(a,measure(path,reverse=reverse))
    a.store.close();a=StructuralProApp(tmp_path/'data')
    assert len(a.open_project('p')['takeoffs'])==1
    assert a.open_project('p')['boq'][0]['quantity']==pytest.approx(9)
    a.store.close()


def test_distinct_geometry_same_quantity_is_not_a_duplicate(tmp_path):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path)
    commit(a,measure(path,10));commit(a,measure(path,20))
    a.store.close();a=StructuralProApp(tmp_path/'data')
    rows=a.open_project('p')['takeoffs'];assert len(rows)==2
    assert rows[0]['source_id']!=rows[1]['source_id']
    assert all(r['params']['source_sha256'] for r in rows)
    assert a.open_project('p')['boq'][0]['quantity']==pytest.approx(18)
    a.store.close()


@pytest.mark.parametrize('tamper',['unit','scale','scale_reference'])
def test_tampered_unit_or_calibration_is_rejected(tmp_path,tamper):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path);s=measure(path);payload=s.to_dict()
    if tamper=='unit':payload['items'][0]['unit']='m2'
    else:
        payload['calibrations']['1']['meters_per_pixel']=.2
        if tamper=='scale_reference':payload['items'][0]['quantity']*=2
    with pytest.raises(ValueError):a.save_drawing_takeoff_session('p',payload)
    assert not a.open_project('p')['takeoffs'];a.store.close()


def test_display_counter_does_not_change_physical_measurement_identity(tmp_path):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path)
    first=measure(path);first.edit(first.items[0].id,source='page:1:length:1');commit(a,first)
    other=measure(path);other.edit(other.items[0].id,source='page:1:length:9')
    with pytest.raises(ValueError):commit(a,other)
    assert len(a.open_project('p')['takeoffs'])==1;a.store.close()


def test_spatially_independent_counts_are_preserved(tmp_path):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path)
    for x in [10,20]:
        s=DrawingTakeoffSession(str(path));s.add_count(1,page=1,takeoff_code='COUNT',point=Point(x,10))
        commit(a,s)
    assert len(a.open_project('p')['takeoffs'])==2
    repeat=DrawingTakeoffSession(str(path));repeat.add_count(1,page=1,takeoff_code='COUNT',point=Point(10,10))
    with pytest.raises(ValueError):commit(a,repeat)
    a.store.close()


def test_hash_does_not_make_invalid_cad_bytes_a_valid_drawing(tmp_path):
    path=tmp_path/'bad.dxf';path.write_text('not a CAD drawing')
    a=project(tmp_path)
    with pytest.raises(ValueError):commit(a,measure(path))
    assert not a.open_project('p')['takeoffs'];a.store.close()


def test_legacy_unverified_measurement_cannot_be_silently_billed_again(tmp_path):
    path=tmp_path/'vector.pdf';pdf(path);a=project(tmp_path);commit(a,measure(path))
    stored=a.open_project('p');params=stored['takeoffs'][0]['params']
    params.pop('measurement_identity');params.pop('source_sha256')
    a.store.save('p',stored)
    with pytest.raises(ValueError):commit(a,measure(path))
    assert len(a.open_project('p')['takeoffs'])==1;a.store.close()
