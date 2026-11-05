"""Source-bound provenance triage for legacy MAP/AEC custom DWG objects.

The source class registry is from a previously SHA-bound decoder snapshot,
while record type IDs/bytes must be independently verified from original DWG.
No private handles, hashes, geometry or payloads are returned. Declared DXF
CLASS counts are not verified object instances. No financial authorization.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

MAX_CUSTOM_OBJECTS = 64
MAX_CLASSES = 512


def _handle(value: Any) -> str:
    if not isinstance(value, str) or not value or any(c not in '0123456789abcdefABCDEF' for c in value):
        raise ValueError('Invalid source custom object identity')
    number = int(value, 16)
    if number == 0 or number >= 2**64:
        raise ValueError('Invalid source custom object identity')
    return format(number, 'X')


def _vendor(app: str) -> str:
    if app == 'AcMapDisplayManagement':
        return 'AUTOCAD_MAP_DISPLAY_MANAGEMENT'
    if app.startswith('AecBase40|') and 'Autodesk Architectural Desktop 2005' in app:
        return 'ARCHITECTURAL_DESKTOP_2005_AECBASE40'
    return 'UNKNOWN_VENDOR_REQUIRES_MANUAL_REVIEW'


def audit_custom_class_fidelity(
    source_records: Sequence[Mapping[str, Any]],
    original_class_registry: Sequence[Mapping[str, Any]],
    converted_dxf: Any,
) -> dict[str, Any]:
    """Bounded identity/class lineage check. Source authenticity is caller's duty.

    One source record per distinct class is required in this scoped 8-class
    audit. No claim that non-graphical custom objects cannot affect takeoff.
    """
    if (not isinstance(source_records, (list, tuple)) or not 1 <= len(source_records) <= MAX_CUSTOM_OBJECTS
            or not isinstance(original_class_registry, (list, tuple))
            or not 1 <= len(original_class_registry) <= MAX_CLASSES):
        raise ValueError('Unbounded or missing custom source evidence')
    if not hasattr(converted_dxf, 'classes') or not hasattr(converted_dxf, 'entitydb'):
        raise ValueError('Target DXF needs real class and object registries')
    original_classes: dict[int, Mapping[str, Any]] = {}
    for item in original_class_registry:
        if not isinstance(item, Mapping) or type(item.get('number')) is not int or item['number'] in original_classes:
            raise ValueError('Duplicated or malformed source class registry')
        original_classes[item['number']] = item
    target_classes: dict[str, Any] = {}
    for c in converted_dxf.classes:
        name = str(c.dxf.get('name', ''))
        if not name or name in target_classes:
            raise ValueError('Duplicated or malformed target DXF class registry')
        target_classes[name] = c
    seen_handles: set[str] = set()
    seen_classes: set[int] = set()
    by_vendor: Counter[str] = Counter()
    definition_missing = origin_mismatch = nongraphical = 0
    id_missing = id_present_unverified = claims_without_id = 0
    for r in source_records:
        if not isinstance(r, Mapping) or type(r.get('type_code')) is not int:
            raise ValueError('Missing authenticated original object type')
        h = _handle(r.get('handle'))
        code, name = r['type_code'], r.get('class_name')
        if (h in seen_handles or code in seen_classes or not isinstance(name, str)
                or not name or code not in original_classes):
            raise ValueError('Conflicting original object or class identity')
        seen_handles.add(h)
        seen_classes.add(code)
        original = original_classes[code]
        if name != original.get('dxfname'):
            raise ValueError('Original source record conflicts with class registry')
        app, cpp = original.get('appname'), original.get('cppname')
        if not isinstance(app, str) or not app or not isinstance(cpp, str) or not cpp:
            raise ValueError('Incomplete original custom class origin metadata')
        by_vendor[_vendor(app)] += 1
        target = target_classes.get(name)
        if target is None:
            definition_missing += 1
        else:
            if target.dxf.get('app_name') != app or target.dxf.get('cpp_class_name') != cpp:
                origin_mismatch += 1
            if target.dxf.get('is_an_entity') == 0:
                nongraphical += 1
            declared = target.dxf.get('instance_count')
            if type(declared) is not int or declared < 0:
                raise ValueError('Invalid target class instance declaration')
        if converted_dxf.entitydb.get(h) is None:
            id_missing += 1
            if target is not None and int(target.dxf.get('instance_count')) > 0:
                claims_without_id += 1
        else:
            # Handle presence alone is not proprietary class or byte fidelity.
            id_present_unverified += 1
    return {
        'policy': 'p8p2_original_custom_class_vendor_and_instance_triage_v1',
        'source_custom_record_count': len(seen_handles),
        'source_vendor_family_counts': dict(sorted(by_vendor.items())),
        'known_vendor_family_identified': 'UNKNOWN_VENDOR_REQUIRES_MANUAL_REVIEW' not in by_vendor,
        'target_dxf_class_definitions_missing': definition_missing,
        'target_dxf_class_origin_mismatches': origin_mismatch,
        'target_dxf_nongraphical_class_declarations': nongraphical,
        'original_instance_identifiers_missing_in_dxf': id_missing,
        'original_instance_identifiers_present_payload_unverified': id_present_unverified,
        'claimed_positive_class_count_but_original_instance_id_missing': claims_without_id,
        'all_source_instance_payloads_verified': False,
        'all_source_custom_reference_links_verified': False,
        'class_non_graphical_proves_irrelevance_to_takeoff': False,
        'automatic_object_enabler_selected': False,
        'automatic_reconstruction_authorized': False,
        'financial_quantity_approved': False,
        'status': ('CUSTOM_CLASS_OR_INSTANCES_MISSING_NO_GO'
                   if id_missing or definition_missing or origin_mismatch
                   else 'SOURCE_IDS_PRESENT_CUSTOM_CONTENT_UNVERIFIED_NO_GO'),
    }
