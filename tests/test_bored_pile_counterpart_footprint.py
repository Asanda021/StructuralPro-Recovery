"""Version-bound separate geometry document; synthetic evidence, no payment clearance."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.bored_pile_counterpart_footprint import (
    POLICY, FOOTPRINT, bind_draft,
)
from test_bored_pile_spatial_overlap import case, audit
from test_bored_pile_joint_real_application import _saved_joint_case
from test_bored_pile_real_application_controller import _document


def make_source(path, data, *, project_id='P', coordinate_ref='COORD',
                datum='Z', xmin='-1', xmax='1', ymin='-1', ymax='1'):
    g = data['geometry']
    kind=data['kind']
    doc = {
        'policy':POLICY, 'project_id':project_id,
        'kind':kind, 'floor_id':data['floor_id'],'member_id':data['member_id'],
        'physical_id':g['physical_cap_id'] if kind=='pile_cap' else g['physical_column_id'],
        'coordinate_ref':coordinate_ref, 'vertical_datum_ref':datum,
        'geometry_source_ref':g['source_ref'], 'geometry_source_sha256':g['source_sha256'],
        'prepared_by':'ProofAuthor', 'reviewer':'ProofIndependentReviewer',
        'x_min_m':xmin,'x_max_m':xmax,'y_min_m':ymin,'y_max_m':ymax,
        'width_m':'2','depth_m':'2',
        'top_elevation_m':g['top_elevation_m'],
        'bottom_elevation_m':g['bottom_elevation_m'],
    }
    path.write_text(json.dumps(doc,sort_keys=True,ensure_ascii=False),encoding='utf-8')
    return doc


def bound_case(tmp_path, *, only_cap=False):
    parts=case(tmp_path)
    for i, (record_name, part_name) in enumerate((('CAP','cap'),('COLUMN','col'))):
        if only_cap and record_name=='COLUMN':continue
        record=parts[4]['reviewed_structural_members'][record_name]
        path=tmp_path/(part_name+'.json')
        make_source(path,record['data'])
        source=deepcopy(record['data'])
        record['data']=bind_draft(source,'P',str(path),reference='سند مستقل افقی '+part_name)
        assert FOOTPRINT not in source['geometry']
        parts[3]['interfaces'][i]['other_record_sha256']=_digest(record)
        parts[5]['links'][i]['other_record_sha256']=_digest(record)
    return parts


def test_legacy_document_is_not_silently_promoted(tmp_path):
    got=audit(case(tmp_path),tmp_path/'original.json')
    assert got['counterpart_geometry_record_bound'] is False
    assert got['unbound_counterpart_count']==2
    assert any('مرز افقی' in b for b in got['blockers'])
    assert not got['commit_allowed'] and not got['ready_for_boq'] and got['rows']==[]


def test_bound_cap_and_column_are_verified_but_finance_is_blocked(tmp_path):
    parts=bound_case(tmp_path);before=deepcopy(parts)
    got=audit(parts,tmp_path/'spatial.json')
    assert got['counterpart_geometry_record_bound'] is True
    assert got['unbound_counterpart_count']==0
    assert len(got['matched_interfaces'])==2
    assert got['status']=='SPATIAL_PREVIEW_ONLY'
    assert not got['commit_allowed'] and not got['ready_for_boq'] and got['rows']==[]
    assert parts==before


def test_partial_bound_is_not_all_members_verified(tmp_path):
    got=audit(bound_case(tmp_path,only_cap=True),tmp_path/'partial.json')
    assert got['counterpart_geometry_record_bound'] is False
    assert got['unbound_counterpart_count']==1


@pytest.mark.parametrize('edit', [
    lambda p:p[5]['links'][0].update(other_x_min_m='-0.9'),
    lambda p:p[5]['links'][0].update(other_y_max_m='1.1'),
    lambda p:p[5]['links'][0].update(other_top_m='0'),
    lambda p:p[4]['reviewed_structural_members']['CAP']['data']['geometry'][FOOTPRINT].update(x_max_m='2'),
    lambda p:p[4]['reviewed_structural_members']['CAP']['data']['geometry'][FOOTPRINT].update(coordinate_ref='OTHER'),
    lambda p:p[4]['reviewed_structural_members']['CAP']['data']['geometry'][FOOTPRINT].update(sha256='0'*64),
    lambda p:p[4]['reviewed_structural_members']['CAP']['data']['geometry'][FOOTPRINT].update(path='/missing/geometry.json'),
])
def test_doc_record_and_calculation_divergence_fails_closed(tmp_path,edit):
    p=bound_case(tmp_path)
    edit(p)
    # Re-pin the simulated audit links after a record edit: changing record
    # digest alone cannot hide a disagreement with its source document.
    record=p[4]['reviewed_structural_members']['CAP']
    p[3]['interfaces'][0]['other_record_sha256']=_digest(record)
    p[5]['links'][0]['other_record_sha256']=_digest(record)
    with pytest.raises(OwnershipError):audit(p,tmp_path/'bad.json')


def test_file_tampering_after_version_pin_fails(tmp_path):
    p=bound_case(tmp_path)
    path=p[4]['reviewed_structural_members']['CAP']['data']['geometry'][FOOTPRINT]['path']
    with open(path,'ab') as f:f.write(b'\n')
    with pytest.raises(OwnershipError):audit(p,tmp_path/'tampered.json')


@pytest.mark.parametrize('defect',[ 'kind','physical_id','floor_id','source_sha','source_ref',
                                      'coordinate_ref','bad_dimension','wrong_section_width','reviewer','float'])
def test_untrusted_document_cannot_be_bound_to_member(tmp_path, defect):
    p=case(tmp_path)
    source=p[4]['reviewed_structural_members']['CAP']['data']
    path=tmp_path/'source.json'
    doc=make_source(path,source)
    if defect=='kind':doc['kind']='column'
    elif defect=='physical_id':doc['physical_id']='different'
    elif defect=='floor_id':doc['floor_id']='WRONG'
    elif defect=='source_sha':doc['geometry_source_sha256']='c'*64
    elif defect=='source_ref':doc['geometry_source_ref']='fake'
    elif defect=='coordinate_ref':doc['coordinate_ref']=''
    elif defect=='bad_dimension':doc['x_min_m']='3'
    elif defect=='wrong_section_width':doc['width_m']='4'
    elif defect=='reviewer':doc['reviewer']='ProofAuthor'
    elif defect=='float':doc['x_min_m']=0.5
    path.write_text(json.dumps(doc),encoding='utf-8')
    with pytest.raises(OwnershipError):bind_draft(source,'P',str(path),reference='Evidence')
    assert FOOTPRINT not in source['geometry']


def test_explicit_binding_refuses_silent_overwrite(tmp_path):
    p=bound_case(tmp_path)
    source=p[4]['reviewed_structural_members']['CAP']['data']
    with pytest.raises(OwnershipError,match='اصلاحیه'):
        bind_draft(source,'P',source['geometry'][FOOTPRINT]['path'],reference='again')


def test_actual_sqlite_versioned_member_and_controller_crosswalk(tmp_path):
    from app.bored_pile_draft_controller import PileDraftController
    from core.platform.application import StructuralProApp
    from core.takeoff.bored_pile_spatial_overlap import POLICY as SPATIAL_POLICY

    app, controller, pile, compiled, owner, joint, snapshot = _saved_joint_case(tmp_path)
    cap_record=next(r for r in snapshot['reviewed_structural_members'].values()
                    if r['data']['kind']=='pile_cap')
    data=cap_record['data']
    path=tmp_path/'cap-source.json'
    make_source(path,data,coordinate_ref=pile['datum']['coordinate_ref'],
                datum=pile['datum']['vertical_datum_ref'])
    prepared=bind_draft(data,'P',str(path),reference='ثبت مستند در نسخه تازه')
    assert data['geometry'].get(FOOTPRINT) is None
    record=app.save_structural_member_draft('P',prepared,expected_revision=cap_record['revision'],
                                             reason='افزودن مرز افقی مستقل')
    assert record['revision']==cap_record['revision']+1
    joint['interfaces'][0]['other_revision']=record['revision']
    joint['interfaces'][0]['other_record_sha256']=_digest(record)
    controller.attach_joint(_document(tmp_path/'joint-current.json',joint),reference='Joint current')
    controller.save()
    link=joint['interfaces'][0]
    doc={'policy':SPATIAL_POLICY, 'project_id':'P','floor_id':'FND','group_id':'PG1',
         'input_sha256':compiled['source_sha256'],
         'coordinate_ref':pile['datum']['coordinate_ref'],
         'vertical_datum_ref':pile['datum']['vertical_datum_ref'],
         'prepared_by':'SpatialAuthor','reviewer':'SpatialIndependentReviewer',
         'links':[{
             'pile_id':pile['piles'][0]['id'], 'pile_physical_id':pile['piles'][0]['physical_id'],
             'other_kind':link['other_kind'], 'other_floor_id':link['other_floor_id'],
             'other_member_id':link['other_member_id'],
             'other_physical_id':link['other_physical_id'],
             'other_record_sha256':link['other_record_sha256'],
             'other_revision':link['other_revision'],
             'pile_center_x_m':'0','pile_center_y_m':'0',
             'other_x_min_m':'-1', 'other_y_min_m':'-1','other_x_max_m':'1','other_y_max_m':'1',
             'other_top_m':link['other_top_m'],'other_bottom_m':link['other_bottom_m'],
             'geometry_reference':link['geometry_reference'],
             'geometry_sha256':link['geometry_sha256'],
             'deduction_id':link['deduction_id'],
         }]}
    snap=deepcopy(app.open_project('P'))
    try:
        result=controller.audit_spatial(_document(tmp_path/'spatial-current.json',doc))
        assert result['counterpart_geometry_record_bound'] is True
        assert result['unbound_counterpart_count']==0
        assert result['rows']==[] and not result['commit_allowed']
        assert app.open_project('P')==snap
        assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert app.open_project('P')['structural_member_history']
    finally:app.store.close()
    reopened=StructuralProApp(tmp_path/'db')
    try:
        again=PileDraftController(reopened,'P')
        again.load('FND','PG1')
        actual=again.audit_spatial(str(tmp_path/'spatial-current.json'))
        assert actual['counterpart_geometry_record_bound'] is True
        assert reopened.open_project('P')['boq']==[]
        assert reopened.open_project('P')['takeoffs']==[]
    finally:reopened.store.close()
