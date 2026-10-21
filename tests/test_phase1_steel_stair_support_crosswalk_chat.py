"""Non-financial steel-stair support evidence tests on real AEC snapshots.

Synthetic bytes and pinned snapshot identities demonstrate validation behavior;
they are never structural-design certification or a project payment ledger.
"""
from copy import deepcopy
from hashlib import sha256

import pytest

from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.steel_stair_support_crosswalk_chat import POLICY, audit
from test_column_joint_preflight_phase1 import sample_project
from test_phase1_steel_stair_preflight_chat import schedule

DRAWING = b'synthetic drawing bytes; NOT signed design'
CONTACT_A = b'synthetic stair-to-column interface; NOT signed'
CONTACT_B = b'synthetic stair-to-beam interface; NOT signed'


def example():
    project = sample_project()
    stair = schedule()
    stair['source']['sha256'] = sha256(DRAWING).hexdigest()
    stringer = deepcopy(stair['groups']['stringers']['entries'][0])
    stringer['id'] = 'ST-STR-02'
    stringer['source_ref'] = 'steel-section-detail-2'
    stringer['scope_ref'] = 'stair-scope-stringer-2'
    stair['groups']['stringers']['entries'].append(stringer)
    stair['ownership']['claims'].append({
        'physical_id': stringer['id'], 'building_id': stair['building_id'],
        'owner_system': stair['system_id'], 'payer_system': stair['system_id'],
        'scope_ref': stringer['scope_ref'], 'source_ref': stringer['source_ref'],
        'approved_by': 'ownership-reviewer'})
    c = project['reviewed_structural_members']['c']
    b = project['beam_detail_register']['b']
    link_c = {'record': {'role': 'column', 'kind': 'column', 'floor_id': 'L1',
               'member_id': 'C1', 'physical_id': 'COL-PH', 'record_revision': 1,
               'record_sha256': _digest(c)},
              'interface_id': 'JOINT-C', 'interface_ref': 'synthetic-column-detail',
              'interface_sha256': sha256(CONTACT_A).hexdigest(),
              'approved_by': 'interface-reviewer',
              'contacts': [{'physical_id': 'ST-STR-01', 'scope_ref': 'stair-scope-stringer'}]}
    link_b = {'record': {'role': 'counterpart', 'kind': 'beam', 'floor_id': 'L1',
               'member_id': 'B1', 'physical_id': 'BEAM-PH', 'record_revision': 2,
               'record_sha256': _digest(b)},
              'interface_id': 'JOINT-B', 'interface_ref': 'synthetic-beam-detail',
              'interface_sha256': sha256(CONTACT_B).hexdigest(),
              'approved_by': 'interface-reviewer',
              'contacts': [{'physical_id': 'ST-STR-02', 'scope_ref': 'stair-scope-stringer-2'}]}
    doc = {'policy': POLICY, 'project_id': 'P', 'building_id': 'BUILDING-A',
           'stair_id': 'STAIR-A', 'floor_id': 'L1',
           'source_sha256': stair['source']['sha256'],
           'prepared_by': 'detail-author', 'reviewer': 'independent-reviewer',
           'links': [link_c, link_b]}
    files = {link_c['interface_sha256']: CONTACT_A,
             link_b['interface_sha256']: CONTACT_B}
    return doc, stair, project, files


def run(doc, stair, project, files, drawing=DRAWING):
    return audit(doc, stair, project, drawing_bytes=drawing, interface_bytes=files)


def test_pinned_real_snapshot_and_document_bytes_still_nonpayable():
    doc, stair, project, files = example()
    before = deepcopy((doc, stair, project, files))
    out = run(doc, stair, project, files)
    assert out['support_evidence_checked'] is True
    assert len(out['bound_supports']) == 2
    assert {x['support_physical_id'] for x in out['bound_supports']} == {'COL-PH', 'BEAM-PH'}
    assert out['ready'] is False and out['commit_allowed'] is False
    assert out['payable_rows'] == [] and out['blockers']
    assert (doc, stair, project, files) == before


@pytest.mark.parametrize('mutation', [
    lambda d,s,p,f: d.update(project_id='ANOTHER-PROJECT'),
    lambda d,s,p,f: d.update(building_id='ANOTHER-BUILDING'),
    lambda d,s,p,f: d.update(stair_id='STAIR-B'),
    lambda d,s,p,f: d.update(floor_id='L2'),
    lambda d,s,p,f: d.update(source_sha256='0'*64),
    lambda d,s,p,f: d.update(policy='unknown-v0'),
    lambda d,s,p,f: d.update(prepared_by='independent-reviewer'),
    lambda d,s,p,f: d['links'][0]['record'].update(record_revision=2),
    lambda d,s,p,f: d['links'][1]['record'].update(record_sha256='f'*64),
    lambda d,s,p,f: d['links'][0]['record'].update(physical_id='COL-OTHER'),
    lambda d,s,p,f: d['links'][1]['record'].update(kind='column'),
    lambda d,s,p,f: d['links'][0]['record'].update(role='counterpart'),
    lambda d,s,p,f: d['links'][1].update(interface_id='JOINT-C'),
    lambda d,s,p,f: d['links'][0].update(interface_sha256='f'*64),
    lambda d,s,p,f: d['links'][0].update(approved_by='detail-author'),
    lambda d,s,p,f: d['links'][0]['contacts'][0].update(scope_ref='OUTSIDE-SCOPE'),
    lambda d,s,p,f: d['links'][0]['contacts'][0].update(physical_id='ANOTHER-STAIR'),
    lambda d,s,p,f: d['links'][1]['contacts'][0].update(physical_id='ST-STR-01'),
    lambda d,s,p,f: d['links'][1].update(contacts=[]),
    lambda d,s,p,f: d['links'].pop(),
    lambda d,s,p,f: d['links'].clear(),
    lambda d,s,p,f: s['groups']['stringers']['entries'][0]['details'].update(count='1.5'),
    lambda d,s,p,f: p['reviewed_structural_members']['c']['data']['geometry'].update(physical_id='NEW-ID'),
    lambda d,s,p,f: p['reviewed_structural_members']['c']['data']['source'].update(approved_by='independent-reviewer'),
    lambda d,s,p,f: p['takeoffs'].append({'params':{'physical_component_id':'ST-STR-01'}}),
    lambda d,s,p,f: p['beam_detail_register'].update(other=deepcopy(p['beam_detail_register']['b'])),
])
def test_invalid_identity_link_revision_or_duplicate_fails_closed(mutation):
    doc, stair, project, files = example()
    mutation(doc, stair, project, files)
    out = run(doc, stair, project, files)
    assert not out['support_evidence_checked']
    assert out['bound_supports'] == []
    assert out['ready'] is False and out['commit_allowed'] is False
    assert out['payable_rows'] == [] and out['blockers']


@pytest.mark.parametrize('payload', [b'tampered', b'', b'x'*(4*1024*1024+1)])
def test_source_bytes_must_be_actual_and_sha_pinned(payload):
    doc, stair, project, files = example()
    out = run(doc, stair, project, files, drawing=payload)
    assert not out['support_evidence_checked'] and not out['bound_supports']
    assert out['payable_rows'] == []


@pytest.mark.parametrize('payload', [None, b'tampered', b''])
def test_interface_bytes_must_be_present_and_verified(payload):
    doc, stair, project, files = example()
    files[doc['links'][0]['interface_sha256']] = payload
    out = run(doc, stair, project, files)
    assert not out['support_evidence_checked'] and not out['bound_supports']
    assert out['payable_rows'] == []


def test_snapshot_staleness_without_revision_change_is_detected():
    doc, stair, project, files = example()
    project['reviewed_structural_members']['c']['data']['source']['plan_revision'] = 'new'
    out = run(doc, stair, project, files)
    assert not out['support_evidence_checked'] and out['payable_rows'] == []


def test_missing_member_registry_is_not_a_valid_empty_building():
    doc, stair, project, files = example()
    project['reviewed_structural_members'] = {}
    assert not run(doc, stair, project, files)['support_evidence_checked']


def test_extra_document_keys_are_not_accepted_as_false_signoff():
    doc, stair, project, files = example()
    doc['accepted_for_payment'] = True
    out = run(doc, stair, project, files)
    assert not out['support_evidence_checked'] and out['payable_rows'] == []
