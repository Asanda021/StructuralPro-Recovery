"""Synthetic cross-member contract tests; not engineering or payment acceptance."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.takeoff.bored_pile_joint_crosswalk import (
    POLICY, OwnershipError, audit_joint_contract, _digest,
)


H = 'a' * 64
E = 'b' * 64


def fixture():
    pile = {
        'id':'BP1', 'physical_id':'PILE-PH', 'top_elevation_m':'-1.0',
        'bottom_elevation_m':'-11.0', 'diameter_m':'0.8',
        'interface': {'pile_cap_id':'CAP1','column_id':'COL1',
                      'ownership_status':'documented_deductions'},
        'deductions':[{'id':'CAPCUT','other_physical_id':'CAP-PH','owner':'other_member',
                       'volume_m3':'0.15','source_ref':'drawing-intersection','approved_by':'Designer'}],
        'rebars': {'longitudinal':{'status':'not_applicable'},
                   'spiral_ties':{'status':'not_applicable'},
                   'crossties':{'status':'not_applicable'},
                   'starters':{'status':'confirmed','series':[{'physical_id':'SERIES','count':'2',
                       'approved_by':'Engineer','unit_weight_ref':'bar-sha','cut_length_ref':'cut-sha'}]}}
    }
    data={'project_id':'P','floor_id':'FND','group_id':'PG1',
          'datum':{'coordinate_ref':'COORD','vertical_datum_ref':'Z','axis_ref':'A'},
          'source':{'approved_by':'Designer'}, 'piles':[pile]}
    compiled={'source_sha256':H,'rows':[
        {'pile_id':'BP1','kind':'concrete_net','physical_id':'PILE-PH:concrete','quantity':'4.1','unit':'m3'},
        {'pile_id':'BP1','kind':'rebar_starters','physical_id':'SERIES','quantity':'7.3','unit':'kg'}]}
    allocations=[
        {'pile_id':'BP1','operation':'concrete_net','physical_id':'PILE-PH:concrete',
         'scope_id':'PILE-CONE','payer_kind':'pile','payer_id':'PILE-PH','bar_piece_ids':[],
         'evidence_ref':'drawing','evidence_sha256':E},
        {'pile_id':'BP1','operation':'rebar_starters','physical_id':'SERIES',
         'scope_id':'STARTER-SCOPE','payer_kind':'other_member','payer_id':'CAP-PH',
         'bar_piece_ids':['BAR-1','BAR-2'],'evidence_ref':'rebar-schedule','evidence_sha256':E},
    ]
    ownership={'schema':'bored_pile_ownership_preflight_v1','project_id':'P','floor_id':'FND',
        'group_id':'PG1','input_sha256':H,'coordinate_ref':'COORD',
        'prepared_by':'OwnershipAuthor','reviewer':'OwnershipReviewer','allocations':allocations}
    cap={'status':'draft','revision':2, 'data':{'kind':'pile_cap','floor_id':'FND','member_id':'CAP1',
         'geometry':{'physical_cap_id':'CAP-PH','top_elevation_m':'-0.50','bottom_elevation_m':'-2.00','source_ref':'signed-geometry','source_sha256':E},
         'rebars':{'starters':{'series':[{'physical_id':'GROUP-CAP','bar_piece_ids':['BAR-1','BAR-2']}]}}}}
    col={'status':'committed','revision':1, 'data':{'kind':'column','floor_id':'FND','member_id':'COL1',
         'geometry':{'physical_column_id':'COL-PH','top_elevation_m':'1','bottom_elevation_m':'0','source_ref':'signed-geometry','source_sha256':E},
         'rebars':{}}}
    project={'id':'P','reviewed_structural_members':{'CAP':cap,'COLUMN':col},'boq':[],'takeoffs':[]}
    def link(record,other_kind,other_id,physical,status,otop,obottom,vol,deduction,owner):
        return {'pile_id':'BP1','other_kind':other_kind,'other_floor_id':'FND',
                'other_member_id':other_id,'other_physical_id':physical,
                'other_record_sha256':_digest(record),'other_revision':record['revision'],
                'geometry_reference':'signed-geometry','geometry_sha256':E,
                'spatial_status':status,'pile_top_m':'-1','pile_bottom_m':'-11',
                'other_top_m':otop,'other_bottom_m':obottom,
                'overlap_volume_m3':vol,'deduction_id':deduction,'allocation_owner':owner}
    links=[link(cap,'pile_cap','CAP1','CAP-PH','documented_deduction','-0.50','-2.00','0.15','CAPCUT','other_member'),
           link(col,'column','COL1','COL-PH','documented_no_overlap','1','0','0','none','not_applicable')]
    transfers=[{'pile_id':'BP1','bar_piece_id':piece,'other_kind':'pile_cap',
                'other_floor_id':'FND','other_member_id':'CAP1','other_bar_physical_id':piece,
                'payer_kind':'other_member','source_ref':'signed-bar-schedule','source_sha256':E}
               for piece in ('BAR-1','BAR-2')]
    joint={'policy':POLICY,'project_id':'P','floor_id':'FND','group_id':'PG1',
           'input_sha256':H,'ownership_sha256':E,'coordinate_ref':'COORD','vertical_datum_ref':'Z',
           'prepared_by':'JointAuthor','reviewer':'JointReviewer',
           'interfaces':links,'bar_transfers':transfers}
    return data,compiled,ownership,joint,project


def check(*parts):
    return audit_joint_contract(parts[0],parts[1],parts[2],E,parts[3],parts[4])


def test_documented_cap_overlap_column_nonoverlap_and_starters_still_no_money():
    inputs=fixture()
    original=deepcopy(inputs)
    r=check(*inputs)
    assert r['status']=='JOINT_CROSSWALK_PREVIEW_ONLY'
    assert not r['ready_for_boq'] and not r['commit_allowed'] and r['rows']==[]
    assert len(r['matched_interfaces'])==2 and r['matched_starter_pieces']==2
    assert r['blockers'] and original == inputs


def test_historical_rows_remain_untouched_and_block_payment():
    i=list(fixture());i[4]['boq']=[{'source_id':'legacy', 'quantity':'77'}]
    r=check(*i)
    assert any('سوابق مالی' in s for s in r['blockers'])
    assert i[4]['boq']==[{'source_id':'legacy','quantity':'77'}]
    assert not r['ready_for_boq']


@pytest.mark.parametrize('mutate', [
    lambda x: x[3].update(project_id='OTHER'),
    lambda x: x[4].update(id='OTHER'),
    lambda x: x[3].update(group_id='WRONG'),
    lambda x: x[3].update(input_sha256='f'*64),
    lambda x: x[3].update(ownership_sha256='f'*64),
    lambda x: x[3].update(coordinate_ref='OTHER'),
    lambda x: x[3].update(vertical_datum_ref='OTHER'),
    lambda x: x[3].update(reviewer='JointAuthor'),
    lambda x: x[3].update(reviewer='OwnershipReviewer'),
    lambda x: x[3]['interfaces'].pop(),
    lambda x: x[3]['interfaces'].append(deepcopy(x[3]['interfaces'][0])),
    lambda x: x[3]['interfaces'][0].update(other_member_id='MISSING'),
    lambda x: x[3]['interfaces'][0].update(other_physical_id='OTHER'),
    lambda x: x[3]['interfaces'][0].update(other_record_sha256='e'*64),
    lambda x: x[3]['interfaces'][0].update(other_revision=1),
    lambda x: x[3]['interfaces'][0].update(pile_top_m='-2'),
    lambda x: x[3]['interfaces'][0].update(other_bottom_m='-1'),
    lambda x: x[3]['interfaces'][1].update(spatial_status='documented_deduction'),
    lambda x: x[3]['interfaces'][0].update(spatial_status='documented_no_overlap'),
    lambda x: x[3]['interfaces'][0].update(overlap_volume_m3='0.16'),
    lambda x: x[3]['interfaces'][0].update(overlap_volume_m3=0.15),
    lambda x: x[3]['interfaces'][0].update(overlap_volume_m3='NaN'),
    lambda x: x[3]['interfaces'][0].update(deduction_id='WRONG'),
    lambda x: x[3]['interfaces'][0].update(allocation_owner='pile'),
    lambda x: x[3]['interfaces'][1].update(overlap_volume_m3='0.01'),
    lambda x: x[3]['interfaces'][1].update(other_top_m='-0.5'),
    lambda x: x[3]['interfaces'][0].update(geometry_sha256='bad'),
    lambda x: x[3]['interfaces'][0].update(geometry_reference='fake-geometry'),
    lambda x: x[3]['interfaces'][0].update(geometry_sha256='c'*64),
    lambda x: x[2]['allocations'][1].update(payer_id='WRONG-CAP'),
    lambda x: x[3]['bar_transfers'].pop(),
    lambda x: x[3]['bar_transfers'].append(deepcopy(x[3]['bar_transfers'][0])),
    lambda x: x[3]['bar_transfers'][0].update(other_member_id='OTHER'),
    lambda x: x[3]['bar_transfers'][0].update(other_bar_physical_id='NONEXISTENT'),
    lambda x: x[3]['bar_transfers'][0].update(payer_kind='pile'),
    lambda x: x[2]['allocations'][1].update(payer_kind='pile',payer_id='PILE-PH'),
    lambda x: x[3]['bar_transfers'][0].update(source_sha256='invalid'),
    lambda x: x[4]['reviewed_structural_members'].pop('CAP'),
    lambda x: x[4]['reviewed_structural_members']['CAP']['data']['geometry'].pop('physical_cap_id'),
    lambda x: x[4]['reviewed_structural_members']['COLUMN']['data']['geometry'].update(bottom_elevation_m='-2'),
    lambda x: x[4]['reviewed_structural_members']['CAP']['data']['rebars']['starters']['series'][0].update(bar_piece_ids=['BAR-1','BAR-1']),
    lambda x: x[0]['piles'][0]['deductions'].append({'id':'OTHER','other_physical_id':'CAP-PH','owner':'other_member','volume_m3':'0.1'}),
])
def test_invalid_links_or_shared_bar_fail_closed(mutate):
    parts=list(fixture());mutate(parts)
    with pytest.raises(OwnershipError):check(*parts)


def test_no_column_is_a_valid_explicit_none_not_an_inferred_column():
    parts=list(fixture()); parts[0]['piles'][0]['interface']['column_id']='none'
    parts[3]['interfaces'].pop()
    r=check(*parts)
    assert len(r['matched_interfaces'])==1 and not r['commit_allowed']


def test_no_starters_with_explicit_not_applicable_requires_zero_transfers():
    parts=list(fixture());parts[0]['piles'][0]['rebars']['starters']={'status':'not_applicable'}
    parts[1]['rows'].pop()
    parts[2]['allocations'].pop()
    parts[3]['bar_transfers']=[]
    r=check(*parts)
    assert r['matched_starter_pieces']==0 and not r['ready_for_boq']


def test_signed_geometry_digest_is_bound_to_canonical_member_record():
    parts=list(fixture());p=parts[4]
    cap=p['reviewed_structural_members']['CAP']
    cap['data']['geometry']['bottom_elevation_m']='-3'
    parts[3]['interfaces'][0]['other_bottom_m']='-3'
    with pytest.raises(OwnershipError):check(*parts)
    parts[3]['interfaces'][0]['other_record_sha256']=_digest(cap)
    r=check(*parts)
    assert r['matched_interfaces'][0]['record_revision']==2
    assert not r['ready_for_boq']


def test_real_external_bar_never_migrates_or_changes_source():
    parts=list(fixture())
    p=parts[4];original=deepcopy(p)
    check(*parts)
    assert p==original


def test_duplicated_piece_in_third_member_fails_closed():
    parts=list(fixture())
    extra=deepcopy(parts[4]['reviewed_structural_members']['CAP'])
    extra['data']['member_id']='UNRELATED'
    extra['data']['geometry']['physical_cap_id']='ANOTHER-CAP'
    parts[4]['reviewed_structural_members']['OTHER']=extra
    with pytest.raises(OwnershipError):check(*parts)


def test_target_record_requires_same_reference_and_digest_as_joint_evidence():
    parts=list(fixture())
    parts[4]['reviewed_structural_members']['CAP']['data']['geometry']['source_sha256']='0'*64
    parts[3]['interfaces'][0]['other_record_sha256']=_digest(parts[4]['reviewed_structural_members']['CAP'])
    with pytest.raises(OwnershipError):check(*parts)


@pytest.mark.parametrize('alias_kind,alias_floor,alias_location', [
    ('pile_cap', 'FND', 'physical_cap_id'),
    ('pile_cap', 'F2', 'physical_cap_id'),
    ('column', 'F2', 'physical_column_id'),
    ('column', 'F2', 'physical_id'),
])
def test_target_physical_identity_cannot_be_aliased_to_another_member(
        alias_kind, alias_floor, alias_location):
    parts = list(fixture())
    project = parts[4]
    alias = deepcopy(project['reviewed_structural_members']['CAP'])
    alias['data']['kind'] = alias_kind
    alias['data']['member_id'] = 'ALIAS-MEMBER'
    alias['data']['floor_id'] = alias_floor
    alias['data']['geometry'] = {'top_elevation_m': '0', 'bottom_elevation_m': '-2'}
    location = alias['data'] if alias_location == 'physical_id' else alias['data']['geometry']
    location[alias_location] = 'CAP-PH'
    project['reviewed_structural_members']['ALIAS'] = alias
    original = deepcopy(parts)
    with pytest.raises(OwnershipError, match='هویت فیزیکی.*تکرار'):
        check(*parts)
    assert parts == original  # Reject without altering the financial ledger.


def test_unicode_normalized_cross_member_physical_alias_is_blocked():
    parts = list(fixture())
    project = parts[4]
    cap = project['reviewed_structural_members']['CAP']
    cap['data']['geometry']['physical_cap_id'] = 'CAP-کی'
    parts[3]['interfaces'][0]['other_physical_id'] = 'CAP-کی'
    cap['data']['rebars']['starters']['series'][0]['bar_piece_ids'] = ['BAR-1','BAR-2']
    parts[2]['allocations'][1]['payer_id'] = 'CAP-کی'
    parts[3]['interfaces'][0]['other_record_sha256'] = _digest(cap)
    other = deepcopy(cap)
    other['data']['member_id'] = 'CAP-ALIAS'
    other['data']['geometry']['physical_cap_id'] = 'CAP-كي'
    project['reviewed_structural_members']['ALIAS'] = other
    with pytest.raises(OwnershipError, match='هویت فیزیکی.*تکرار'):
        check(*parts)


def test_distinct_target_physical_id_in_unrelated_member_is_not_conflict():
    parts = list(fixture())
    project = parts[4]
    separate = deepcopy(project['reviewed_structural_members']['CAP'])
    separate['data']['member_id'] = 'CAP-UNRELATED'
    separate['data']['geometry']['physical_cap_id'] = 'UNRELATED-PH'
    separate['data']['rebars']['starters']['series'][0]['bar_piece_ids'] = []
    project['reviewed_structural_members']['ANOTHER'] = separate
    result = check(*parts)
    assert result['rows'] == [] and result['commit_allowed'] is False
