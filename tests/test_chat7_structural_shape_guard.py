"""Reviewed columns and footings must specify their actual physical shape."""
import pytest
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_structural import empty_member, preview_member
from core.platform.application import StructuralProApp

@pytest.mark.parametrize('kind,dims',[('column',{'width':.4,'depth':.5,'height':3}),
                                      ('isolated_footing',{'length':2,'width':2,'thickness':.5}),
                                      ('pile_cap',{'length':2,'width':2,'thickness':.7}),
                                      ('tie_beam',{'length':5,'width':.4,'depth':.5})])
def test_missing_shape_does_not_infer_rectangular_member(kind,dims):
    data=empty_member(kind,'L1','S1')
    data['source']={'mode':'manual','source_id':'synthetic:member:S1'}
    data['geometry']={'count':1,'source_ref':'detail:S1',
                      'approved_by':'synthetic:reviewer','intersections':[],**dims}
    result=preview_member(data,TakeoffEngine())
    assert not result['ready']
    assert any('نوع هندسه' in blocker for blocker in result['blockers'])
    assert not [row for row in result['rows'] if row.get('code')=='concrete']


def test_invalid_member_shape_never_commits_to_project(tmp_path):
    a=StructuralProApp(tmp_path)
    a.create_project('سازه آزمایشی','P')
    member=a.new_structural_member('column','L1','C1')
    member['source']={'mode':'manual','source_id':'synthetic:column:C1'}
    member['geometry']={'width':.4,'depth':.4,'height':3,'count':1,
                        'source_ref':'detail:C1','approved_by':'reviewer','intersections':[]}
    preview=preview_member(member,TakeoffEngine())
    assert not preview['ready']
    assert a.open_project('P')['boq']==[]
    a.store.close()
