"""Synthetic-only custom-source class registry tests; no private CAD."""
from types import SimpleNamespace

import pytest

from core.drawings.dwg_map_aec_vendor_triage import audit_custom_class_fidelity


class _Class:
    def __init__(self, **fields):
        self.dxf = SimpleNamespace(get=lambda k, default=None: fields.get(k, default))


def evidence(*, missing=False, count=1, wrong_app=False, restored_id=False):
    source = [
        {'handle': 'A', 'type_code': 514, 'class_name': 'DMMAPMANAGER'},
        {'handle': 'B', 'type_code': 521, 'class_name': 'AEC_VARS_DWG_SETUP'},
    ]
    classes = [
        {'number': 514, 'dxfname': 'DMMAPMANAGER',
         'cppname': 'AcMapDMMapManager', 'appname': 'AcMapDisplayManagement'},
        {'number': 521, 'dxfname': 'AEC_VARS_DWG_SETUP',
         'cppname': 'AecDbVarsDwgSetup',
         'appname': 'AecBase40|Product Desc: Autodesk Architectural Desktop 2005'},
    ]
    target = [
        _Class(name=x['dxfname'], cpp_class_name=x['cppname'],
               app_name=('WRONG_ORIGIN' if wrong_app else x['appname']),
               is_an_entity=0, instance_count=count) for x in classes
    ]
    if missing:
        target.pop()
    dxf = SimpleNamespace(
        classes=target,
        entitydb={'A': object(), 'B': object()} if restored_id else {},
    )
    return source, classes, dxf


def test_two_distinct_vendor_families_and_false_class_count():
    r = audit_custom_class_fidelity(*evidence())
    assert r['source_custom_record_count'] == 2
    assert r['source_vendor_family_counts'] == {
        'ARCHITECTURAL_DESKTOP_2005_AECBASE40': 1,
        'AUTOCAD_MAP_DISPLAY_MANAGEMENT': 1,
    }
    assert r['target_dxf_nongraphical_class_declarations'] == 2
    assert r['original_instance_identifiers_missing_in_dxf'] == 2
    assert r['claimed_positive_class_count_but_original_instance_id_missing'] == 2
    assert r['class_non_graphical_proves_irrelevance_to_takeoff'] is False
    assert r['financial_quantity_approved'] is False
    assert 'A' not in r and 'B' not in r


def test_count_zero_does_not_hide_original_missing_instances():
    r = audit_custom_class_fidelity(*evidence(count=0))
    assert r['original_instance_identifiers_missing_in_dxf'] == 2
    assert r['claimed_positive_class_count_but_original_instance_id_missing'] == 0
    assert r['status'] == 'CUSTOM_CLASS_OR_INSTANCES_MISSING_NO_GO'


def test_original_id_present_does_not_certify_bytes_or_links():
    r = audit_custom_class_fidelity(*evidence(restored_id=True))
    assert r['original_instance_identifiers_missing_in_dxf'] == 0
    assert r['original_instance_identifiers_present_payload_unverified'] == 2
    assert r['status'] == 'SOURCE_IDS_PRESENT_CUSTOM_CONTENT_UNVERIFIED_NO_GO'
    assert r['all_source_custom_reference_links_verified'] is False
    assert r['automatic_reconstruction_authorized'] is False


def test_class_missing_detected():
    r = audit_custom_class_fidelity(*evidence(missing=True))
    assert r['target_dxf_class_definitions_missing'] == 1


def test_wrong_origin_detected():
    r = audit_custom_class_fidelity(*evidence(wrong_app=True))
    assert r['target_dxf_class_origin_mismatches'] == 2


@pytest.mark.parametrize('change', [
    'duplicated_id', 'duplicate_class', 'wrong_source_class', 'invalid_id',
    'missing_type', 'blank_source_app', 'repeated_registry_code',
    'target_class_missing', 'invalid_instance_count', 'no_source_records',
])
def test_reject_incomplete_or_contradictory_source_claims(change):
    source, registry, dxf = evidence()
    if change == 'duplicated_id':
        source[1]['handle'] = '000A'
    elif change == 'duplicate_class':
        source[1]['type_code'] = 514
        source[1]['class_name'] = 'DMMAPMANAGER'
    elif change == 'wrong_source_class':
        source[0]['class_name'] = 'NOT_THE_ORIGINAL_CLASS'
    elif change == 'invalid_id':
        source[0]['handle'] = 'INVALID'
    elif change == 'missing_type':
        source[1].pop('type_code')
    elif change == 'blank_source_app':
        registry[0]['appname'] = ''
    elif change == 'repeated_registry_code':
        registry.append(dict(registry[0]))
    elif change == 'target_class_missing':
        dxf = SimpleNamespace(entitydb={})
    elif change == 'invalid_instance_count':
        r = registry[0]
        dxf.classes[0] = _Class(name=r['dxfname'],
                                app_name=r['appname'],
                                cpp_class_name=r['cppname'],
                                is_an_entity=0, instance_count=-1)
    else:
        source = []
    with pytest.raises(ValueError):
        audit_custom_class_fidelity(source, registry, dxf)
