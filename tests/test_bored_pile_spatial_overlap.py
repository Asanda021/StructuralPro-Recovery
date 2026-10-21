"""Bounded source-pinned 3D bored-pile/box intersection; never BOQ clearance."""
from copy import deepcopy
from decimal import Decimal, Context, localcontext
from hashlib import sha256
import json

import pytest

from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.bored_pile_spatial_overlap import (
    POLICY, cylinder_box_overlap, audit_spatial_overlap,
)
from core.takeoff.bored_pile_specialist_chat import PI
from test_bored_pile_joint_crosswalk import fixture, E


def volume_of_contained_pile():
    with localcontext(Context(prec=256)):
        return format(PI*Decimal('0.4')**2, 'f')


def case(tmp_path):
    data,compiled,ownership,joint,project = deepcopy(fixture())
    vol = volume_of_contained_pile()
    data['piles'][0]['deductions'][0]['volume_m3']=vol
    joint['interfaces'][0]['overlap_volume_m3']=vol
    proof = {
        'policy':POLICY, 'project_id':'P','floor_id':'FND','group_id':'PG1',
        'input_sha256':compiled['source_sha256'], 'coordinate_ref':'COORD',
        'vertical_datum_ref':'Z', 'prepared_by':'SpatialAuthor',
        'reviewer':'IndependentSpatialReviewer',
        'links':[]}
    for source_link in joint['interfaces']:
        proof['links'].append({
            'pile_id':source_link['pile_id'], 'pile_physical_id':'PILE-PH',
            'other_kind':source_link['other_kind'],
            'other_floor_id':source_link['other_floor_id'],
            'other_member_id':source_link['other_member_id'],
            'other_physical_id':source_link['other_physical_id'],
            'other_record_sha256':source_link['other_record_sha256'],
            'other_revision':source_link['other_revision'],
            'pile_center_x_m':'0','pile_center_y_m':'0',
            'other_x_min_m':'-1','other_y_min_m':'-1',
            'other_x_max_m':'1','other_y_max_m':'1',
            'other_top_m':source_link['other_top_m'],
            'other_bottom_m':source_link['other_bottom_m'],
            'geometry_reference':source_link['geometry_reference'],
            'geometry_sha256':source_link['geometry_sha256'],
            'deduction_id':source_link['deduction_id']})
    return data,compiled,ownership,joint,project,proof


def audit(parts, path):
    *inputs, proof = parts
    raw=json.dumps(proof, ensure_ascii=False,sort_keys=True, separators=(',',':')).encode()
    path.write_bytes(raw)
    return audit_spatial_overlap(*inputs[:3], E, inputs[3],inputs[4],
                                 evidence_path=str(path), evidence_sha256=sha256(raw).hexdigest())


def test_bound_cylinder_in_cap_spatial_crosswalk_is_still_preview_only(tmp_path):
    parts=case(tmp_path);before=deepcopy(parts)
    r=audit(parts,tmp_path/'spatial.json')
    assert r['status']=='SPATIAL_PREVIEW_ONLY'
    assert not r['ready_for_boq'] and not r['commit_allowed'] and r['rows']==[]
    assert r['matched_interfaces'][0]['horizontal_case']=='cylinder_inside_box'
    assert Decimal(r['matched_interfaces'][0]['overlap_volume_m3']) == Decimal(volume_of_contained_pile())
    assert r['matched_interfaces'][1]['horizontal_case']=='z_disjoint'
    assert parts==before


def test_box_strictly_inside_cylinder_is_exact_rectangular_intersection():
    pile={'diameter_m':'2','top_elevation_m':'0','bottom_elevation_m':'-2'}
    got=cylinder_box_overlap(pile,center_x_m='0',center_y_m='0',
                             box_x_min_m='-0.2',box_y_min_m='-0.2',
                             box_x_max_m='0.2',box_y_max_m='0.2',
                             box_top_m='0',box_bottom_m='-1')
    assert got=={'horizontal_case':'box_inside_cylinder','overlap_volume_m3':'0.16',
                 'overlap_height_m':'1','area_m2':'0.16'}


@pytest.mark.parametrize('box', [
    ('2','-1','3','1'),
    ('1','1','2','2'),
    ('0.4','0.1','1','1'),
])
def test_xy_disjoint_including_tangency(box):
    pile={'diameter_m':'0.8','top_elevation_m':'0','bottom_elevation_m':'-2'}
    got=cylinder_box_overlap(pile,center_x_m='0',center_y_m='0',
                             box_x_min_m=box[0],box_y_min_m=box[1],
                             box_x_max_m=box[2],box_y_max_m=box[3],
                             box_top_m='0',box_bottom_m='-1')
    assert got['overlap_volume_m3']=='0'
    assert got['horizontal_case']=='xy_disjoint'


@pytest.mark.parametrize('bad', [
    dict(center_x_m=0.0),dict(center_x_m=True),
    dict(box_x_min_m='NaN'),dict(box_y_max_m='Infinity'),
    dict(box_top_m='-4',box_bottom_m='-3'),
    dict(box_x_min_m='2',box_x_max_m='1'),
    dict(box_x_min_m='0.2',box_x_max_m='1'),
])
def test_unknown_or_unsupported_geometry_fails_closed(bad):
    pile={'diameter_m':'0.8','top_elevation_m':'0','bottom_elevation_m':'-2'}
    kwargs=dict(center_x_m='0',center_y_m='0',box_x_min_m='-1',
                box_y_min_m='-1',box_x_max_m='1',box_y_max_m='1',
                box_top_m='0',box_bottom_m='-1')
    kwargs.update(bad)
    with pytest.raises(OwnershipError):cylinder_box_overlap(pile,**kwargs)


@pytest.mark.parametrize('mutate', [
    lambda p: p[5].update(project_id='wrong'),
    lambda p: p[5].update(coordinate_ref='wrong'),
    lambda p: p[5].update(vertical_datum_ref='wrong'),
    lambda p: p[5].update(input_sha256='f'*64),
    lambda p: p[5].update(reviewer='SpatialAuthor'),
    lambda p: p[5].update(reviewer='JointReviewer'),
    lambda p: p[5].update(reviewer='Designer'),
    lambda p: p[5]['links'].pop(),
    lambda p: p[5]['links'].append(deepcopy(p[5]['links'][0])),
    lambda p: p[5]['links'][0].update(other_record_sha256='e'*64),
    lambda p: p[5]['links'][0].update(other_revision=3),
    lambda p: p[5]['links'][0].update(other_top_m='2'),
    lambda p: p[5]['links'][0].update(geometry_sha256='f'*64),
    lambda p: p[5]['links'][0].update(other_physical_id='DIFFERENT'),
    lambda p: p[5]['links'][0].update(other_x_min_m='0'),
    lambda p: p[5]['links'][0].update(pile_center_x_m='0.75'),
    lambda p: p[5]['links'][0].update(other_x_max_m=1.0),
    lambda p: p[5]['links'][0].update(deduction_id='wrong'),
    lambda p: p[3]['interfaces'][0].update(overlap_volume_m3='0.15'),
    lambda p: p[0]['piles'][0]['deductions'][0].update(volume_m3='0.15'),
    lambda p: p[4]['reviewed_structural_members']['CAP']['data']['geometry'].update(source_ref='tampered'),
])
def test_any_unbound_identity_or_wrong_volume_blocks_all_results(tmp_path, mutate):
    parts=case(tmp_path);mutate(parts)
    with pytest.raises(OwnershipError):audit(parts,tmp_path/'bad.json')


def test_tampered_spatial_file_sha_rejected(tmp_path):
    parts=case(tmp_path)
    path=tmp_path/'source.json'
    audit(parts,path)
    digest=sha256(path.read_bytes()).hexdigest()
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):
        audit_spatial_overlap(*parts[:3],E,parts[3],parts[4],
                              evidence_path=str(path), evidence_sha256=digest)


def test_numerical_deduction_remains_separate_from_other_member_payment(tmp_path):
    parts=case(tmp_path)
    parts[4]['boq']=[{'id':'HISTORIC','quantity':'83'}]
    parts[4]['takeoffs']=[{'id':'HISTORIC-ROW'}]
    before=deepcopy(parts[4])
    r=audit(parts,tmp_path/'persisted.json')
    assert not r['ready_for_boq'] and r['rows']==[]
    assert parts[4]==before


def test_second_positive_volume_same_z_is_conservatively_blocked(tmp_path,monkeypatch):
    parts=case(tmp_path)
    col=parts[4]['reviewed_structural_members']['COLUMN']
    col['data']['geometry']['top_elevation_m']='-1'
    col['data']['geometry']['bottom_elevation_m']='-2'
    cap_volume=volume_of_contained_pile()
    parts[3]['interfaces'][1].update(
        other_top_m='-1',other_bottom_m='-2',
        other_record_sha256=_digest(col),spatial_status='documented_deduction',
        overlap_volume_m3=cap_volume,deduction_id='COLCUT',
        allocation_owner='other_member')
    parts[0]['piles'][0]['deductions'].append({
        'id':'COLCUT','other_physical_id':'COL-PH','volume_m3':cap_volume,
        'owner':'other_member','source_ref':'drawing','approved_by':'Designer'})
    parts[5]['links'][1].update(other_top_m='-1',other_bottom_m='-2',
                              other_record_sha256=_digest(col),deduction_id='COLCUT')
    # Baseline will reject independently if a complete finance/member contract
    # cannot establish this triple; spatial layer has its own conservative gate.
    import core.takeoff.bored_pile_spatial_overlap as spatial
    monkeypatch.setattr(spatial, 'audit_joint_contract', lambda *_: {
        'ready_for_boq':False,'commit_allowed':False,'rows':[]})
    with pytest.raises(OwnershipError, match='سه‌طرفه'):
        audit(parts,tmp_path/'threeway.json')
