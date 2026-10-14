"""Source-backed circular-column/spiral takeoff acceptance, Chat 2026-10-14.

All source references/engineering inputs are explicitly synthetic and are not
an engineer's approval or a real building design.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
import sqlite3
import pytest

from core.takeoff.reviewed_structural import preview_member
from core.takeoff.engine import TakeoffEngine
from core.platform.application import StructuralProApp

PI = Decimal('3.14159265358979323846264338327950288419716939937510')


def synthetic_column():
    def missing():
        return {'status':'not_applicable','source_ref':'D-synthetic','approved_by':'reviewer-synthetic','reason':'Explicitly not applicable in synthetic case'}
    diameter=Decimal('.4');height=Decimal('3')
    return {
        'kind':'column','floor_id':'L1','member_id':'C-round','building_id':'B1','axis':'A1',
        'measurement_policy':'column_specialist_v1',
        'source':{'mode':'manual','source_id':'test:circular:C-round','plan_ref':'P-synthetic','detail_ref':'D-synthetic'},
        'geometry':{'shape':'circular_column','diameter':'0.4','height':'3','count':'2',
                    'variable_units':{'diameter':'m','height':'m','count':'عدد'},
                    'repeat_scope':'identical_members','source_ref':'D-synthetic','approved_by':'reviewer-synthetic',
                    'intersection_ref':'no intersections per source','intersection_scope':'total_group','intersections':[]},
        'formwork':{'status':'confirmed','source_ref':'D-synthetic','approved_by':'reviewer-synthetic',
                    'area_scope':'per_member','area_scope_ref':'per member',
                    'surfaces':[{'id':'wall','role':'curved_wall','coverage':'full_lateral','area_method':'circular_lateral',
                                 'contact':True,'source_ref':'D-synthetic','approved_by':'reviewer-synthetic',
                                 'deductions':[]}]},
        'rebars':{
            'longitudinal':{'status':'confirmed','source_ref':'D-synthetic','approved_by':'reviewer-synthetic',
                            'count_scope':'per_member','count_scope_ref':'per member',
                            'segments':[{'id':'L1','count':'6','nominal_diameter_mm':'16','shape_ref':'D-longitudinal',
                                         'cut_length_m':'3.4','cut_length_ref':'D-cut','unit_weight_kg_m':'1.58',
                                         'unit_weight_source':'reviewed-catalog','source_ref':'D-synthetic',
                                         'approved_by':'reviewer-synthetic'}]},
            'ties':missing(), 'crossties':missing(), 'starters':missing()
        }
    }


def spiral_segment(identifier,start,end,pitch,turns):
    return {'id':identifier,'shape_kind':'spiral','start_m':start,'end_m':end,
            'pitch_m':pitch,'turns':turns,'axis_diameter_m':'0.32',
            'cover_m':'0.035','count':1,'nominal_diameter_mm':'10',
            'shape_ref':'D-spiral','cut_length_ref':'D-spiral-cut',
            'end_parts_m':[],'end_condition':'no_extension_reviewed',
            'end_condition_ref':'D-ends','unit_weight_kg_m':'0.617',
            'unit_weight_source':'reviewed-catalog','source_ref':'D-spiral',
            'approved_by':'reviewer-synthetic'}


def with_spiral(data=None):
    d=deepcopy(data if data is not None else synthetic_column())
    d['rebars']['ties']={'status':'confirmed','source_ref':'D-spiral','approved_by':'reviewer-synthetic',
                        'count_scope':'per_member','count_scope_ref':'per member',
                        'segments':[spiral_segment('SP1','0','1','.1',10),spiral_segment('SP2','1','3','.2',10)]}
    return d


def quantities(report):
    return {r['source_id'].split(':')[-1]:Decimal(str(r['quantity'])) for r in report['rows']}


def test_circle_explicit_pi_and_independent_concrete_formwork_longitudinal():
    d=synthetic_column();r=preview_member(d,TakeoffEngine());assert r['ready'],r['blockers']
    q=quantities(r)
    with localcontext() as ctx:
        ctx.prec=120
        assert q['concrete']==PI*Decimal('.4')**2/4*Decimal('3')*2
        assert q['formwork']==PI*Decimal('.4')*Decimal('3')*2
    assert q['longitudinal']==Decimal('6')*Decimal('3.4')*Decimal('1.58')*2
    assert 'pi_policy' in r['rows'][0]['params']


def test_spiral_two_explicit_zones_no_boundary_double_count():
    r=preview_member(with_spiral(),TakeoffEngine());assert r['ready'],r['blockers']
    q=quantities(r);expected=Decimal(0)
    with localcontext() as ctx:
        ctx.prec=120
        for pitch in (Decimal('.1'),Decimal('.2')):
            with localcontext() as root_ctx:
                root_ctx.prec=50
                root=((PI*Decimal('.32'))**2+pitch**2).sqrt()
            expected += Decimal(10)*root
        expected*=Decimal('0.617')*2
    assert abs(q['ties']-expected)<Decimal('1e-45')


@pytest.mark.parametrize('change',[
    lambda d:d['geometry'].update(diameter='0'),
    lambda d:d['geometry'].update(diameter='Infinity'),
    lambda d:d['geometry']['variable_units'].update(diameter='m2'),
    lambda d:d['formwork']['surfaces'][0].update(coverage='unknown'),
    lambda d:d['formwork']['surfaces'][0].update(contact=None),
    lambda d:d['rebars']['ties']['segments'][0].update(turns=9),
    lambda d:d['rebars']['ties']['segments'][0].update(pitch_m='0'),
    lambda d:d['rebars']['ties']['segments'][0].update(axis_diameter_m='0.4'),
    lambda d:d['rebars']['ties']['segments'][0].update(cover_m='0.05'),
    lambda d:d['rebars']['ties']['segments'][1].update(start_m='0.9'),
    lambda d:d['rebars']['ties']['segments'][1].update(id='SP1'),
    lambda d:d['rebars']['ties']['segments'][0].update(end_parts_m=[{'kind':'hook','length_m':'.1'}]),
    lambda d:d['rebars']['ties']['segments'][0].update(cut_length_m='10'),
])
def test_circular_contract_fail_closed(change):
    d=with_spiral();change(d)
    assert not preview_member(d,TakeoffEngine())['ready']


def test_circular_sqlite_boq_and_protected_committed_revisions(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('پروژه آزمایشی','P');d=with_spiral()
    draft=app.save_structural_member_draft('P',d,expected_revision=0)
    assert draft['revision']==1
    r=app.preview_structural_member('P','column','L1','C-round');assert r['ready'],r['blockers']
    app.commit_structural_member('P','column','L1','C-round',expected_revision=1)
    p=app.open_project('P');baseline=deepcopy(p['takeoffs']);old=deepcopy(p['reviewed_structural_members']);assert any(row['unit']=='kg' for row in p['boq'])
    with pytest.raises(ValueError):app.save_structural_member_draft('P',d,expected_revision=1)
    d2=deepcopy(d);d2['geometry']['diameter']='0.5'
    # Once the circular contract has its own reviewed amendment, it must not mutate issued finance.
    assert hasattr(app,'create_column_amendment')
    app.store.close()
    reopened=StructuralProApp(tmp_path)
    p2=reopened.open_project('P');assert p2['takeoffs']==baseline and p2['reviewed_structural_members']==old
    for path in tmp_path.rglob('*.db'):
        with sqlite3.connect(path) as db:assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    reopened.store.close()


def test_circle_deductions_and_amendment_preserve_source_and_finance(tmp_path):
    service=StructuralProApp(tmp_path)
    service.create_project('داده آزمایشی','P')
    d=with_spiral()
    d['geometry']['intersections']=[{'id':'opening-1','volume_m3':'0.01','source_ref':'detail-open-1','approved_by':'reviewer-synthetic'}]
    assert preview_member(d,TakeoffEngine())['ready']
    service.save_structural_member_draft('P',d,expected_revision=0)
    service.commit_structural_member('P','column','L1','C-round',expected_revision=1)
    old=deepcopy(service.open_project('P'))
    new=deepcopy(d)
    new['geometry']['diameter']='0.5'
    for spiral in new['rebars']['ties']['segments']:
        spiral['axis_diameter_m']='0.42'
    assert preview_member(new,TakeoffEngine())['ready']
    amended=service.create_column_amendment('P','L1','C-round',new,expected_revision=1,
        created_by='creator-synthetic',reason='new diameter explicitly documented')
    service.review_beam_amendment('P',amended['id'],expected_revision=1,
        reviewer='independent-synthetic',note='reviewed synthetic evidence')
    service.apply_beam_amendment('P',amended['id'],expected_revision=1)
    updated=service.open_project('P')
    assert updated['takeoffs']==old['takeoffs']
    assert updated['reviewed_structural_members']==old['reviewed_structural_members']
    rows={r['unit']:Decimal(str(r['quantity'])) for r in updated['boq']}
    with localcontext() as ctx:
        ctx.prec=120
        expected=PI*Decimal('.5')**2/4*Decimal('3')*2-Decimal('0.01')
    assert rows['m3']==expected
    with pytest.raises((ValueError,RuntimeError)):
        service.apply_beam_amendment('P',amended['id'],expected_revision=1)
    service.store.close()
    service=StructuralProApp(tmp_path)
    assert service.open_project('P')['boq']==updated['boq']
    service.store.close()


def test_explicit_reviewed_spiral_end_lengths_are_not_inferred():
    d=with_spiral()
    s=d['rebars']['ties']['segments'][0]
    s['end_condition']='detailed_extensions'
    s['end_parts_m']=[{'kind':'hook','length_m':'.12','source_ref':'D-hook'},
                       {'kind':'anchorage','length_m':'.06','source_ref':'D-anchorage'}]
    original=preview_member(with_spiral(),TakeoffEngine())
    modified=preview_member(d,TakeoffEngine())
    assert modified['ready'],modified['blockers']
    assert quantities(modified)['ties']-quantities(original)['ties']==Decimal('.18')*Decimal('.617')*2
