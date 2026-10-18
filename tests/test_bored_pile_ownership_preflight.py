"""Synthetic ownership preflight tests; never engineering/financial acceptance."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from core.takeoff.bored_pile_ownership_preflight import (
    SCHEMA, OwnershipError, audit, read_evidence,
)

H = 'a' * 64
E = 'b' * 64


def fixture():
    data = {
        'project_id': 'P', 'floor_id': 'FND', 'group_id': 'PG1',
        'source': {'source_id': 'S1', 'source_ref': 'drawing', 'approved_by': 'Author'},
        'datum': {'coordinate_ref': 'coord-1', 'axis_ref': 'A', 'vertical_datum_ref': 'Z'},
        'piles': [{
            'id': 'BP1', 'physical_id': 'PH1',
            'interface': {'ownership_status': 'review_required', 'pile_cap_id': 'CAP1', 'column_id': 'none', 'approved_by': 'JointAuthor'},
            'rebars': {
                'longitudinal': {'status': 'confirmed', 'series': [{'physical_id': 'REBAR-1', 'count': '2'}]},
                'spiral_ties': {'status': 'not_applicable'},
                'crossties': {'status': 'not_applicable'},
                'starters': {'status': 'not_applicable'},
            },
        }],
    }
    compiled = {'source_sha256': H, 'rows': [
        {'pile_id': 'BP1', 'kind': 'concrete_net', 'physical_id': 'PH1:concrete', 'quantity': '2.0', 'unit': 'm3'},
        {'pile_id': 'BP1', 'kind': 'rebar_longitudinal', 'physical_id': 'REBAR-1', 'quantity': '4.5', 'unit': 'kg'},
    ]}
    alloc = lambda op, pid, scope, pieces: {
        'pile_id': 'BP1', 'operation': op, 'physical_id': pid, 'scope_id': scope,
        'payer_kind': 'pile', 'payer_id': 'PH1', 'bar_piece_ids': pieces,
        'evidence_ref': 'drawing-synthetic', 'evidence_sha256': E,
    }
    evidence = {
        'schema': SCHEMA, 'project_id': 'P', 'floor_id': 'FND', 'group_id': 'PG1',
        'input_sha256': H, 'coordinate_ref': 'coord-1', 'prepared_by': 'Surveyor',
        'reviewer': 'Independent', 'allocations': [
            alloc('concrete_net', 'PH1:concrete', 'concrete-PH1', []),
            alloc('rebar_longitudinal', 'REBAR-1', 'bars-PH1', ['BAR-1', 'BAR-2'])],
    }
    return data, compiled, evidence


def test_read_only_claims_have_no_financial_authority():
    d, c, e = fixture()
    original = deepcopy((d, c, e))
    result = audit(d, c, e)
    assert not result['commit_allowed'] and not result['ready_for_boq']
    assert result['status'] == 'READ_ONLY_PENDING_CROSS_MEMBER_GATE'
    assert len(result['candidate_owned_rows']) == 2
    assert not result['excluded_operations'] and len(result['physical_claims']) == 4
    assert result['blockers'] and (d, c, e) == original


@pytest.mark.parametrize('field,value', [
    ('project_id', 'OTHER'), ('floor_id', 'OTHER'), ('group_id', 'OTHER'),
    ('input_sha256', 'b'*64), ('coordinate_ref', 'other'),
    ('reviewer', 'Author'), ('reviewer', 'surveyor'), ('reviewer', 'JointAuthor'),
    ('schema', 'v0'),
])
def test_invalid_identity_or_independent_reviewer_is_blocked(field, value):
    d, c, e = fixture(); e[field] = value
    with pytest.raises(OwnershipError): audit(d, c, e)


@pytest.mark.parametrize('change', [
    lambda e: e['allocations'][1].update(bar_piece_ids=['BAR-1']),
    lambda e: e['allocations'][1].update(bar_piece_ids=['BAR-1', 'BAR-1']),
    lambda e: e['allocations'][1].update(bar_piece_ids=[]),
    lambda e: e['allocations'][0].update(bar_piece_ids=['BAR-3']),
    lambda e: e['allocations'][1].update(physical_id='SOME-OTHER-REBAR'),
    lambda e: e['allocations'][1].update(payer_id='CAP1'),
    lambda e: e['allocations'][0].update(evidence_sha256='invalid'),
    lambda e: e['allocations'].append(deepcopy(e['allocations'][0])),
    lambda e: e['allocations'][1].update(scope_id=' '),
])
def test_mismatched_allocation_or_duplicate_is_blocked(change):
    d, c, e = fixture(); change(e)
    with pytest.raises(OwnershipError): audit(d, c, e)


def test_other_member_is_informational_not_financial():
    d, c, e = fixture()
    row = e['allocations'][0]
    row['payer_kind'] = 'other_member'; row['payer_id'] = 'CAP1'
    out = audit(d, c, e)
    assert len(out['candidate_owned_rows']) == 1
    assert out['excluded_operations'][0]['reason'] == 'مالک پرداخت عضو دیگر است'
    assert out['ready_for_boq'] is False


def test_missing_allocation_is_unknown_not_zero():
    d, c, e = fixture(); e['allocations'].pop()
    out = audit(d, c, e)
    assert len(out['candidate_owned_rows']) == 1
    assert out['excluded_operations'][0]['operation'] == 'rebar_longitudinal'
    assert 'quantity' not in out['excluded_operations'][0]


def test_duplicate_physical_claim_in_supplied_snapshot_is_blocked():
    d, c, e = fixture()
    with pytest.raises(OwnershipError):
        audit(d, c, e, existing_physical_claims=[('bar', 'bar-1')])


def test_normalization_detects_same_reviewer_in_arabic_script():
    d, c, e = fixture(); e['prepared_by'] = 'كيان'; e['reviewer'] = 'کیان'
    with pytest.raises(OwnershipError): audit(d, c, e)


def test_engine_duplicate_operation_is_rejected():
    d, c, e = fixture(); c['rows'].append(deepcopy(c['rows'][0]))
    with pytest.raises(OwnershipError): audit(d, c, e)


def test_actual_document_hash_check_and_duplicate_json_keys(tmp_path):
    d, c, e = fixture(); path = tmp_path / 'owner.json'
    raw = json.dumps(e, ensure_ascii=False, sort_keys=True).encode()
    path.write_bytes(raw)
    out = read_evidence(path, sha256(raw).hexdigest())
    assert audit(d, c, out)['ready_for_boq'] is False
    with pytest.raises(OwnershipError): read_evidence(path, '0'*64)
    path.write_text('{"schema":"a", "schema":"b"}')
    with pytest.raises(OwnershipError): read_evidence(path, sha256(path.read_bytes()).hexdigest())


def test_float_and_nonfinite_are_not_accepted_in_evidence(tmp_path):
    path = tmp_path / 'evidence.json'
    for s in ('{"a": 1.2}', '{"a": NaN}', '{"a": Infinity}'):
        path.write_text(s)
        with pytest.raises(OwnershipError): read_evidence(path, sha256(path.read_bytes()).hexdigest())
