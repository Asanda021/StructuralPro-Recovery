"""Synthetic cross-registry material identity regression (no engineering approval)."""
from copy import deepcopy
import pytest
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.phase1_shared_materials_audit import POLICY,audit

def scenario():
    project={
        'id':'P','boq':[],'takeoffs':[],
        'reviewed_structural_members':{
            'COLUMN':{'status':'committed','revision':3,
                      'data':{'kind':'column','floor_id':'F1','member_id':'C1'}}},
        'beam_detail_register':{
            'BEAM':{'status':'committed','revision':2,
                    'data':{'floor_id':'F1','beam_id':'B1'}}},
        'reviewed_aec_systems':{
            'ROOF':{'status':'committed','revision':4,
                    'data':{'kind':'waffle','floor_id':'F2','system_id':'R1'}}}}
    def claim(book,material,physical):
        record=next(iter(project[book].values()))
        data=record['data']
        return {
            'material_kind':material,'physical_material_id':physical,
            'member_kind':'beam' if book=='beam_detail_register' else data['kind'],
            'floor_id':data['floor_id'],
            'member_id':data.get('beam_id') or data.get('system_id') or data.get('member_id'),
            'source_ref':'منبع مصنوعی','detail_ref':'دیتایل مصنوعی',
            'member_revision':record['revision'],
            'member_record_sha256':_digest(record)}
    doc={
        'policy':POLICY,'project_id':'P','prepared_by':'Editor',
        'reviewer':'Independent Reviewer','claims':[
            claim('reviewed_structural_members','concrete','C1-CONC'),
            claim('beam_detail_register','rebar','B1-BAR'),
            claim('reviewed_aec_systems','formwork','ROOF-FORM')]}
    return project,doc

def test_all_three_actual_registry_shapes_are_checked_read_only():
    project,document=scenario()
    before=deepcopy((project,document))
    result=audit(project,document)
    assert result['verified_registered_claim_count']==3
    assert result['rows']==[] and result['ready_for_boq'] is False
    assert result['commit_allowed'] is False
    assert (project,document)==before

@pytest.mark.parametrize('fault',[
    'stale_aec','unknown_aec','physical_duplicate','same_member_two_books',
    'invalid_aec_book','bool_revision','missing_aec_data','wrong_project',
    'unauthorized_approval_field',
])
def test_ambiguous_or_stale_owners_fail_closed(fault):
    project,document=scenario()
    if fault=='stale_aec':
        project['reviewed_aec_systems']['ROOF']['revision']=5
    elif fault=='unknown_aec':
        document['claims'][-1]['member_id']='UNKNOWN'
    elif fault=='physical_duplicate':
        document['claims'][-1]['physical_material_id']='C1-CONC'
    elif fault=='same_member_two_books':
        project['reviewed_aec_systems']['ROOF']['data'].update(
            kind='column',floor_id='F1',system_id='C1')
        document['claims'][-1].update(
            member_kind='column',floor_id='F1',member_id='C1')
    elif fault=='invalid_aec_book':
        project['reviewed_aec_systems']=[]
    elif fault=='bool_revision':
        document['claims'][-1]['member_revision']=True
    elif fault=='missing_aec_data':
        del project['reviewed_aec_systems']['ROOF']['data']
    elif fault=='wrong_project':
        document['project_id']='WRONG'
    elif fault=='unauthorized_approval_field':
        document['accepted_for_payment']=True
    with pytest.raises(OwnershipError):
        audit(project,document)

def test_historical_bar_collision_always_requires_independent_review():
    project,document=scenario()
    project['takeoffs']=[{
        'source_id':'T1','params':{'physical_bar_id':'B1-BAR'}}]
    before=deepcopy(project)
    result=audit(project,document)
    assert result['commit_allowed'] is False and result['rows']==[]
    assert any('دوباره‌شماری' in message for message in result['blockers'])
    assert project==before
