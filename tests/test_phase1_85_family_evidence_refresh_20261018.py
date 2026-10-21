"""Fail-closed consistency checks for the 85-family / eight-roof phase-one evidence ledger.

A successful audit test protects *bookkeeping*, not production acceptance.
"""
from collections import Counter
from hashlib import sha1
import json
from pathlib import Path

import pytest

from core.product.aec_item_inventory_audit import verify_priority_inventory


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / 'docs/aec_priority_1_9_master_inventory_20261013.json'
PREVIOUS = ROOT / 'docs/acceptance/aec_85_family_evidence_matrix_8phases_20261016.json'
CURRENT = ROOT / 'docs/acceptance/phase1_85_family_evidence_refresh_20261018.json'


def document(path):
    return json.loads(path.read_text(encoding='utf-8'))


def blob_sha(path):
    data = path.read_bytes()
    return sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


@pytest.fixture(scope='module')
def inputs():
    return document(CURRENT), document(INVENTORY), document(PREVIOUS)


def test_snapshot_sources_are_immutable_and_mapped_to_real_blobs(inputs):
    audit, inventory, previous = inputs
    assert audit['inventory_blob_sha'] == blob_sha(INVENTORY)
    assert audit['previous_matrix_blob_sha'] == blob_sha(PREVIOUS)
    assert audit['inventory_path'] == INVENTORY.relative_to(ROOT).as_posix()
    assert audit['previous_matrix_path'] == PREVIOUS.relative_to(ROOT).as_posix()
    assert audit['snapshot_head'] == '35fa76418041e1aa00ca1ade640c258a8df6dde7'
    assert verify_priority_inventory()['valid']
    assert inventory['priority_family_count'] == previous['source_family_count'] == 85


def test_all_85_codes_unique_with_exact_phase_and_component_count(inputs):
    audit, inventory, previous = inputs
    rows = audit['rows']
    codes = [r['code'] for r in rows]
    assert len(rows) == len(codes) == len(set(codes)) == 85
    inventory_by = {r['code']: r for r in inventory['items']}
    previous_by = {r['code']: r for r in previous['rows']}
    assert set(codes) == set(inventory_by) == set(previous_by)
    assert sum(row['subitem_mentions'] for row in rows) == 879
    for row in rows:
        old, master = previous_by[row['code']], inventory_by[row['code']]
        assert row['title'] == old['title'] == master['title']
        assert row['primary_phase'] == old['primary_phase']
        assert row['inventory_route'] == master['coverage_level']
        assert row['subitem_mentions'] == len(master['components'])
        assert row['historical_status'] == old['acceptance_status']
        assert set(old['evidence'].get('documents', [])).issubset(row['evidence_documents'])
        assert set(old['evidence'].get('tests', [])).issubset(row['evidence_tests'])


def test_phase_counts_do_not_confuse_phase_one_with_the_full_inventory(inputs):
    audit, _, _ = inputs
    count = Counter(str(row['primary_phase']) for row in audit['rows'])
    assert count == {'1':74,'2':3,'3':5,'4':1,'5':1,'7':1}
    assert {str(k):v for k,v in audit['phase_counts'].items()} == dict(count)
    summary = audit['summary']
    assert (summary['families'],summary['phase1_families'],summary['other_phases'],
            summary['subitem_mentions']) == (85,74,11,879)
    phase_one = [r for r in audit['rows'] if r['primary_phase'] == 1]
    assert summary['phase1_evidence_levels'] == dict(Counter(r['evidence_level'] for r in phase_one))
    assert summary['phase1_evidence_levels'] == {
        'historical_limited_evidence':12,
        'no_family_specific_verified_evidence':41,
        'additional_specialist_evidence':21,
    }


def test_roof_variants_exact_and_distinct_from_85_parent_family_codes(inputs):
    audit, inventory, _ = inputs
    expected = [('solid_slab','دال بتنی'),('joist_block','تیرچه‌بلوک'),
                ('joist_foam','تیرچه‌فوم'),('waffle','وافل یک‌طرفه'),
                ('waffle','وافل دوطرفه'),('hollow_core','هالوکور'),
                ('uboot','یوبوت'),('cobiax','کوبیاکس')]
    roof = audit['roof_variants']
    assert [(r['family_code'],r['name']) for r in roof] == expected
    assert len(roof) == audit['summary']['roof_system_variants'] == 8
    assert len(set(r['family_code'] for r in roof)) == audit['summary']['roof_inventory_family_codes'] == 7
    assert {r['family_code'] for r in roof}.issubset({r['code'] for r in inventory['items']})
    assert all(r['full_acceptance'] is False and r['status']=='limited_documented' for r in roof)


@pytest.mark.parametrize('accepted', [False, None, {}, [], 0])
def test_never_use_false_or_unknown_evidence_as_full_acceptance(inputs, accepted):
    audit, _, _ = inputs
    assert audit['summary']['fully_accepted_phase1_families'] == 0
    for r in audit['rows']:
        assert r['fully_accepted'] is False
        assert r['real_project_accepted'] is False
        assert r['windows_office_accepted'] is False
        assert r['tests_reexecuted_for_this_audit'] is False
        assert r['evidence_level'] in {
            'historical_limited_evidence',
            'additional_specialist_evidence',
            'no_family_specific_verified_evidence',
        }


def test_relative_evidence_paths_are_safe_and_traceable(inputs):
    audit, _, _ = inputs
    for row in audit['rows']:
        for name in row['evidence_documents']:
            path = Path(name)
            assert not path.is_absolute() and '..' not in path.parts
            assert name.startswith('docs/acceptance/') and name.endswith('.md')
        for name in row['evidence_tests']:
            path = Path(name)
            assert not path.is_absolute() and '..' not in path.parts
            assert name.startswith('tests/test_') and name.endswith('.py')
