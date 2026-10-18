"""Phase-one documented orthogonal (L-shaped) stone stair landing, no inferred cuts."""
from copy import deepcopy
from decimal import Decimal

import pytest

from core.takeoff.orthogonal_footprint import checked_outline, rectangle_inside
from core.takeoff.stone_stair_finish_detail import ORTHOGONAL_CONTRACT
from test_stone_stair_phase1 import sample, preview, item


def outline(*coords):
    return [dict(x=str(x),y=str(y)) for x,y in coords]


def rectangle(L,W):
    return outline((0,0),(L,0),(L,W),(0,W),(0,0))


L_SHAPE=outline((0,0),(2,0),(2,1),(1,1),(1,2),(0,2),(0,0))


def irregular():
    d=sample();a=d['architecture_detail'];a['contract']=ORTHOGONAL_CONTRACT
    for f in a['faces']:
        f['outline']=rectangle(f['length_m'],f['width_m'])
    landing=next(f for f in a['faces'] if f['id']=='L1')
    landing['width_m']='2';landing['outline']=deepcopy(L_SHAPE)
    a['stocks'].append(item('ST-L1-UP',length_m='1',width_m='1',material_ref=landing['material_ref']))
    a['pieces'].append(item('P-L1-UP',face_id='L1',stock_id='ST-L1-UP',piece_type='full',
                            x='0',y='1',width_m='1',height_m='1',stock_x='0',stock_y='0',
                            cut_ref='برش/جانمایی مستند پاگرد L'))
    return d


def test_documented_l_shaped_landing_and_preserved_original_faces():
    d=irregular();original=deepcopy(d);r=preview(d)
    assert r['ready'],r['blockers']
    paid={row['item_code']:Decimal(str(row['quantity']))
          for row in r['rows'] if row['role']=='work'}
    assert paid=={'tread':Decimal('.30'),'riser':Decimal('.16'),'landing':Decimal(3)}
    landing=next(row for row in r['rows'] if row['item_code']=='landing')
    assert landing['params']['outline']==L_SHAPE
    assert len([row for row in r['rows'] if row['role']=='work'])==3
    assert d==original


def test_exact_l_shape_with_permitted_boundary_contact():
    vertex,area=checked_outline(L_SHAPE,'2','2')
    assert area==3
    assert rectangle_inside(vertex,(Decimal(0),Decimal(0),Decimal(2),Decimal(1)))
    assert rectangle_inside(vertex,(Decimal(0),Decimal(1),Decimal(1),Decimal(2)))
    assert not rectangle_inside(vertex,(Decimal(1),Decimal(1),Decimal(2),Decimal(2)))
    assert not rectangle_inside(vertex,(Decimal('.5'),Decimal('.5'),Decimal('1.5'),Decimal('1.5')))


@pytest.mark.parametrize('change',[
    'nonclosed','diagonal','duplicate_vertex','reversed_segment','float_vertex',
    'bool_vertex','nan','extra_field','out_of_bbox','smaller_bounds',
    'collinear_midpoint','self_touch','removed_outline','invalid_dtype',
    'piece_in_recess','piece_crosses_concavity','opening_in_recess',
    'opening_crosses_concavity','piece_removed','piece_double',
])
def test_bad_geometry_and_undocumented_cut_fails_closed(change):
    d=irregular();a=d['architecture_detail']
    landing=next(f for f in a['faces'] if f['id']=='L1')
    upper=next(p for p in a['pieces'] if p['id']=='P-L1-UP')
    if change=='nonclosed':landing['outline'].pop()
    elif change=='diagonal':landing['outline'][2]['y']='.9'
    elif change=='duplicate_vertex':landing['outline'][4]=deepcopy(landing['outline'][3])
    elif change=='reversed_segment':landing['outline'][4]['x']='2'
    elif change=='float_vertex':landing['outline'][0]['x']=0.0
    elif change=='bool_vertex':landing['outline'][0]['x']=False
    elif change=='nan':landing['outline'][2]['y']='NaN'
    elif change=='extra_field':landing['outline'][0]['z']='0'
    elif change=='out_of_bbox':landing['outline'][2]['x']='3'
    elif change=='smaller_bounds':landing['length_m']='1.5'
    elif change=='collinear_midpoint':landing['outline'].insert(1,{'x':'1','y':'0'})
    elif change=='self_touch':landing['outline'][3]={'x':'0','y':'0'}
    elif change=='removed_outline':landing.pop('outline')
    elif change=='invalid_dtype':landing['outline']='0,0;2,0;2,1;1,1;1,2;0,2'
    elif change=='piece_in_recess':upper.update(x='1',y='1')
    elif change=='piece_crosses_concavity':upper.update(x='.5',y='1')
    elif change=='opening_in_recess':a['openings'].append(item('HOLE',face_id='L1',x='1',y='1',width_m='.5',height_m='.5'))
    elif change=='opening_crosses_concavity':a['openings'].append(item('HOLE',face_id='L1',x='.8',y='.8',width_m='.5',height_m='.5'))
    elif change=='piece_removed':a['pieces'].remove(upper)
    elif change=='piece_double':
        z=deepcopy(upper);z.update(id='P-ADDED',physical_key='P-ADDED');a['pieces'].append(z)
    r=preview(d)
    assert not r['ready'] and r['rows']==[] and r['blockers'],(change,r)


def test_orthogonal_sqlite_review_commit_and_no_material_double_charge(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('نمونه پاگرد L', 'P')
    d=irregular();s=app.save_aec_system_draft('P',d,expected_revision=0)
    assert s['revision']==1
    app.review_roof_system('P','stone_floor','FND','STONE-ST1',expected_revision=1,
                           reviewer='بازبین مستقل هندسه',note='برش و جانمایی مستند')
    receipt=app.commit_aec_system('P','stone_floor','FND','STONE-ST1',expected_revision=2)
    assert receipt['status']=='committed'
    project=app.open_project('P')
    assert len(project['boq'])==3
    assert sum((Decimal(str(r['quantity'])) for r in project['boq']), Decimal(0))==Decimal('3.46')
    assert any(row.get('params',{}).get('geometry_contract')==ORTHOGONAL_CONTRACT
               for row in project['takeoffs'])
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()


def test_legacy_rectangular_contract_remains_unchanged():
    d=sample();r=preview(d)
    assert r['ready']
    assert sum(Decimal(str(x['quantity'])) for x in r['rows'] if x['role']=='work')==Decimal('2.46')


def test_cross_contract_revision_is_blocked():
    from core.takeoff.architecture_detail import validate_amendment
    old=sample();new=irregular()
    with pytest.raises(ValueError,match='قرارداد'):
        validate_amendment(old,new,[],[])



def test_l_shaped_stair_with_full_height_rectangular_cut_and_real_recut():
    d=irregular();a=d['architecture_detail']
    a['openings'].append(item('CUT-OPEN',face_id='L1',x='1',y='0',width_m='.5',height_m='1'))
    a['stocks']=[s for s in a['stocks'] if s['id']!='ST-L1']
    a['pieces']=[p for p in a['pieces'] if p['id']!='P-L1']
    for ident,x,width in [('LEFT','0','1'),('RIGHT','1.5','.5')]:
        a['stocks'].append(item('ST-'+ident,length_m=width,width_m='1',material_ref='سنگ تراورتن مصنوعی'))
        a['pieces'].append(item('P-'+ident,face_id='L1',stock_id='ST-'+ident,
                               piece_type='full',x=x,y='0',width_m=width,height_m='1',
                               stock_x='0',stock_y='0',cut_ref='قطعه واقعی '+ident))
    r=preview(d)
    assert r['ready'],r['blockers']
    assert Decimal(str(next(x for x in r['rows'] if x['item_code']=='landing')['quantity']))==Decimal('2.5')
    assert sum(Decimal(str(row['quantity'])) for row in r['rows'] if row['role']=='work')==Decimal('2.96')


def test_orthogonal_copy_requires_new_review_and_new_physical_claims(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('نسخه کپی L', 'P')
    d=irregular();app.save_aec_system_draft('P',d,expected_revision=0)
    copied=app.aec_workflow().copy_roof('P','stone_floor','FND','STONE-ST1',
        new_system_id='STONE-COPY',new_source_id='SOURCE-COPY',reason='نسخه فیزیکی مستقل')['data']
    assert copied['architecture_detail']['contract']==ORTHOGONAL_CONTRACT
    assert copied['architecture_detail']['geometry']['physical_stair_id']!=d['architecture_detail']['geometry']['physical_stair_id']
    assert copied['architecture_detail']['faces'][2]['outline']==L_SHAPE
    assert not preview(copied)['ready']
    assert app.open_project('P')['boq']==[]
    app.store.close()


def test_winding_direction_does_not_change_area_or_containment():
    original, area1=checked_outline(L_SHAPE,'2','2')
    reverse=list(reversed(L_SHAPE[:-1]));reverse.append(reverse[0])
    changed,area2=checked_outline(reverse,'2','2')
    assert area1==area2==3
    box=(Decimal('0'),Decimal('1'),Decimal('1'),Decimal('2'))
    assert rectangle_inside(original,box) and rectangle_inside(changed,box)
