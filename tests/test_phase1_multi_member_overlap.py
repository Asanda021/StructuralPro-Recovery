"""Orthogonal envelope intersections for versioned synthetic structural members.

No test treats these boxes as concrete, formwork, rebar or payable deductions.
"""
import json
from copy import deepcopy
from hashlib import sha256
from decimal import Decimal

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_beam_panel import PRISM_POLICY, POINTER_KEY
from core.takeoff.phase1_multi_member_overlap import POLICY, preview, preview_file
from test_column_joint_beam_panel_phase1 import case, write


def two(tmp_path):
    project, existing = case(tmp_path)
    doc = {'policy': POLICY, 'project_id': 'P',
           'coordinate_ref': 'GRID-A', 'vertical_datum_ref': 'ELEV-1',
           'detail_ref': 'Synthetic source note',
           'prepared_by': 'EnvelopeAuthor', 'reviewer': 'EnvelopeReviewer',
           'geometry_scope': 'bounding_envelopes_only', 'ownership_status': 'unresolved',
           'links': deepcopy(existing['links']),
           'pair_claims': [{'roles': ['column', 'counterpart'], 'envelope_intersection_m3': '0.16'}],
           'triple_claim_m3': '0'}
    return project, doc


def three(tmp_path):
    project, doc = two(tmp_path)
    column = project['reviewed_structural_members']['c']
    new = deepcopy(column)
    new['data']['member_id'] = 'C-THIRD'
    new['data']['physical_id'] = 'COL-PH-THIRD'
    g = new['data']['geometry']
    g['physical_id'] = 'COL-PH-THIRD'
    g['source_ref'] = 'ThirdIndependentGeometry'
    g['source_sha256'] = 'c' * 64
    bbox = dict(x_min_m='0.1', x_max_m='0.3', y_min_m='-0.1', y_max_m='0.1',
                z_min_m='1.25', z_max_m='1.75')
    source = dict(policy=PRISM_POLICY, project_id='P', role='third', kind='column',
                  floor_id='L1', member_id='C-THIRD', physical_id='COL-PH-THIRD',
                  coordinate_ref='GRID-A', vertical_datum_ref='ELEV-1',
                  geometry_source_ref=g['source_ref'], geometry_source_sha256=g['source_sha256'],
                  prepared_by='ThirdPrismAuthor', reviewer='ThirdPrismReviewer', **bbox)
    path = tmp_path / 'third.json'
    g[POINTER_KEY] = dict(policy=PRISM_POLICY, path=str(path.resolve()), sha256=write(path, source),
                          reference='Third independent prism', coordinate_ref='GRID-A',
                          vertical_datum_ref='ELEV-1', physical_id='COL-PH-THIRD')
    project['reviewed_structural_members']['third'] = new
    doc['links'].append(dict(role='third', kind='column', floor_id='L1',
                             member_id='C-THIRD', physical_id='COL-PH-THIRD',
                             record_revision=new['revision'], record_sha256=_digest(new)))
    doc['pair_claims'] += [
        dict(roles=['column', 'third'], envelope_intersection_m3='0.02'),
        dict(roles=['counterpart', 'third'], envelope_intersection_m3='0.02')]
    doc['triple_claim_m3'] = '0.02'
    return project, doc


def test_two_members_overlap_has_explicit_nonfinancial_bounds(tmp_path):
    project, doc = two(tmp_path)
    saved = deepcopy((project, doc))
    r = preview(doc, project)
    assert r['status'] == 'ENVELOPE_COLLISION_PREVIEW_ONLY'
    assert r['pair_intersections'] == [{'roles': ['column', 'counterpart'], 'envelope_intersection_m3': '0.16'}]
    assert r['triple_intersection_m3'] == '0'
    assert Decimal(r['union_envelope_m3']) == Decimal('2.56')
    assert r['material_deduction_m3'] is None
    assert r['rows'] == [] and r['ready_for_boq'] is False and r['commit_allowed'] is False
    assert (project,doc) == saved


def test_three_members_triple_overlap_is_not_counted_three_times(tmp_path):
    p, d = three(tmp_path)
    out = preview(d, p)
    assert out['member_count'] == 3
    assert len(out['pair_intersections']) == 3
    assert out['triple_intersection_m3'] == '0.0200'
    # Without inclusion-exclusion the 0.02 common to three shapes would be
    # removed once too often by three pairwise subtractions.
    assert Decimal(out['union_envelope_m3']) == Decimal('2.56')
    assert out['material_deduction_m3'] is None and out['rows'] == []


def test_exact_disjoint_and_touching_are_zero(tmp_path):
    p,d = two(tmp_path)
    beam=p['beam_detail_register']['b']
    source_path=tmp_path/'counterpart.json'
    source=json.loads(source_path.read_text())
    source.update(x_min_m='0.4',x_max_m='2.4')
    beam['data']['geometry'][POINTER_KEY]['sha256']=write(source_path,source)
    d['links'][1]['record_sha256']=_digest(beam)
    d['pair_claims'][0]['envelope_intersection_m3']='0'
    out=preview(d,p)
    assert out['pair_intersections'][0]['envelope_intersection_m3']=='0'
    source.update(x_min_m='3',x_max_m='5')
    beam['data']['geometry'][POINTER_KEY]['sha256']=write(source_path,source)
    d['links'][1]['record_sha256']=_digest(beam)
    assert preview(d,p)['pair_intersections'][0]['envelope_intersection_m3']=='0'


def test_finite_exact_precision_no_float_tolerance(tmp_path):
    p,d=two(tmp_path)
    beam=p['beam_detail_register']['b']
    source_path=tmp_path/'counterpart.json'
    source=json.loads(source_path.read_text())
    source.update(x_min_m='-0.00000000000000000000001')
    beam['data']['geometry'][POINTER_KEY]['sha256']=write(source_path,source)
    d['links'][1]['record_sha256']=_digest(beam)
    # An additional 1e-23 m of source-pinned beam crosses the column.
    # This is a real 4e-24 m3 envelope change, never ignored by tolerance.
    d['pair_claims'][0]['envelope_intersection_m3']='0.160000000000000000000004'
    assert Decimal(preview(d,p)['pair_intersections'][0]['envelope_intersection_m3']) == Decimal('0.160000000000000000000004')
    d['pair_claims'][0]['envelope_intersection_m3']='0.160000000000000000000003'
    with pytest.raises(OwnershipError): preview(d,p)


@pytest.mark.parametrize('mode', [
    'wrong_policy','wrong_project','same_reviewer','wrong_scope','pretend_payment',
    'float_quantity','nan_quantity','negative_quantity','bool_quantity','wrong_quantity',
    'missing_pair','duplicate_pair','bad_role_pair','self_pair','missing_link','duplicate_link',
    'same_identity','wrong_revision','wrong_digest','old_prism_digest','missing_prism_file',
    'invalid_datum','new_foreign_key','unverified_third','duplicate_third_identity',
    'wrong_triple','missing_triple_pair','duplicate_third_pair','unverified_member_role',
    'duplicate_other_registry','missing_registry','invalid_record','bad_file_sha',
])
def test_all_unproven_or_ambiguous_claims_fail_closed(tmp_path,mode):
    p,d=three(tmp_path) if mode in ('unverified_third','duplicate_third_identity',
                                  'wrong_triple','missing_triple_pair','duplicate_third_pair') else two(tmp_path)
    if mode=='wrong_policy': d['policy']='unknown'
    elif mode=='wrong_project': d['project_id']='OTHER'
    elif mode=='same_reviewer': d['reviewer']=d['prepared_by']
    elif mode=='wrong_scope': d['geometry_scope']='solid_concrete'
    elif mode=='pretend_payment': d['ownership_status']='approved'
    elif mode=='float_quantity': d['pair_claims'][0]['envelope_intersection_m3']=0.16
    elif mode=='nan_quantity': d['pair_claims'][0]['envelope_intersection_m3']='NaN'
    elif mode=='negative_quantity': d['pair_claims'][0]['envelope_intersection_m3']='-0.16'
    elif mode=='bool_quantity': d['pair_claims'][0]['envelope_intersection_m3']=True
    elif mode=='wrong_quantity': d['pair_claims'][0]['envelope_intersection_m3']='0.159'
    elif mode=='missing_pair': d['pair_claims']=[]
    elif mode=='duplicate_pair': d['pair_claims'].append(deepcopy(d['pair_claims'][0]))
    elif mode=='bad_role_pair': d['pair_claims'][0]['roles']=['column','unknown']
    elif mode=='self_pair': d['pair_claims'][0]['roles']=['column','column']
    elif mode=='missing_link': d['links'].pop()
    elif mode=='duplicate_link': d['links'][1]=deepcopy(d['links'][0])
    elif mode=='same_identity': d['links'][1]['physical_id']=d['links'][0]['physical_id']
    elif mode=='wrong_revision': d['links'][0]['record_revision']+=1
    elif mode=='wrong_digest': d['links'][0]['record_sha256']='f'*64
    elif mode=='old_prism_digest': p['reviewed_structural_members']['c']['data']['geometry'][POINTER_KEY]['sha256']='f'*64
    elif mode=='missing_prism_file': (tmp_path/'column.json').unlink()
    elif mode=='invalid_datum': d['vertical_datum_ref']='wrong'
    elif mode=='new_foreign_key': d['material_qty']='99'
    elif mode=='unverified_third': d['links'][2]['member_id']='MISSING'
    elif mode=='duplicate_third_identity': d['links'][2]['physical_id']=d['links'][0]['physical_id']
    elif mode=='wrong_triple': d['triple_claim_m3']='0.01'
    elif mode=='missing_triple_pair': d['pair_claims'].pop()
    elif mode=='duplicate_third_pair': d['pair_claims'][2]=deepcopy(d['pair_claims'][1])
    elif mode=='unverified_member_role': d['links'][0]['role']='owner'
    elif mode=='duplicate_other_registry':
        p['reviewed_structural_members']['alias']={'data':{'geometry':{'physical_id':'BEAM-PH'}}}
    elif mode=='missing_registry': p['beam_detail_register']={}
    elif mode=='invalid_record': p['reviewed_structural_members']['c']='broken'
    elif mode=='bad_file_sha':
        path=tmp_path/'column.json';path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError): preview(d,p)


def test_independent_source_bytes_and_real_sqlite_reopen(tmp_path):
    app=StructuralProApp(tmp_path/'db'); app.create_project('سناریوی منشور آزمایشی','P')
    project,doc=two(tmp_path)
    snapshot=app.open_project('P')
    snapshot.update({name:deepcopy(project[name]) for name in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',snapshot)
    saved=app.open_project('P');before=deepcopy(saved)
    path=tmp_path/'collision.json';digest=write(path,doc)
    out=preview_file(saved,str(path),digest)
    assert out['rows']==[] and out['material_deduction_m3'] is None
    assert app.open_project('P')==before
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()
    second=StructuralProApp(tmp_path/'db')
    try:
        assert second.open_project('P')==before
        assert preview(doc,second.open_project('P'))['ready_for_boq'] is False
        changed=second.open_project('P');changed['beam_detail_register']['b']['revision']+=1
        second.store.save('P',changed)
        with pytest.raises(OwnershipError):preview(doc,second.open_project('P'))
    finally:second.store.close()
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(before,str(path),digest)


def test_column_footing_face_contact_is_not_positive_overlap(tmp_path):
    from test_column_joint_footing_tie_phase1 import fixture as footing_case
    project, face = footing_case(tmp_path)
    d = {'policy': POLICY, 'project_id': 'P',
         'coordinate_ref': 'COORD', 'vertical_datum_ref': 'DATUM',
         'detail_ref': 'Footing + column synthetic contact',
         'prepared_by': 'EnvelopeAuthor', 'reviewer': 'EnvelopeReviewer',
         'geometry_scope': 'bounding_envelopes_only', 'ownership_status': 'unresolved',
         'links': deepcopy(face['links']),
         'pair_claims': [{'roles': ['column', 'counterpart'], 'envelope_intersection_m3': '0'}],
         'triple_claim_m3': '0'}
    result = preview(d, project)
    assert result['pair_intersections'][0]['envelope_intersection_m3'] == '0'
    assert Decimal(result['union_envelope_m3']) == Decimal('3.92')
    assert result['material_deduction_m3'] is None and result['rows'] == []
