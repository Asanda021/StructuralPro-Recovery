"""Source-bound read-only comparison of opaque DWG decoder objects vs produced DXF.

IMPORTANT: This is a cross-output consistency check on one LibreDWG decoding
pipeline. It is not an independent DWG decoder and NEVER authorizes takeoff.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Mapping, Any


def _handle_of(value: object) -> str:
    if isinstance(value, str):
        return value.upper()
    return str(value.dxf.handle).upper()


def audit_opaque_conversion_loss(original_dwg: str | Path, converted_dxf: str | Path,
                                 earlier_ledger: Mapping[str, Any]) -> dict[str, Any]:
    """Identify missing opaque records and broken direct DICTIONARY references.

    External ledger must have been independently frozen to disk earlier; its
    origin remains LibreDWG. Hash mismatches or unexpected class/owner
    relationships are *errors*, never proof of success.
    """
    import ezdxf
    original_dwg, converted_dxf = Path(original_dwg), Path(converted_dxf)
    if original_dwg.suffix.lower() != '.dwg' or not original_dwg.is_file():
        raise ValueError('Original DWG is absent')
    if converted_dxf.suffix.lower() != '.dxf' or not converted_dxf.is_file():
        raise ValueError('Converted DXF is absent')
    if not 6 < original_dwg.stat().st_size < 50 * 1024 * 1024:
        raise ValueError('Invalid DWG byte size')
    if not 100 < converted_dxf.stat().st_size < 250 * 1024 * 1024:
        raise ValueError('Invalid DXF byte size')
    source_sha = sha256(original_dwg.read_bytes()).hexdigest()
    dxf_sha = sha256(converted_dxf.read_bytes()).hexdigest()
    if earlier_ledger.get('source_sha256') != source_sha:
        raise ValueError('Original DWG differs from frozen audit')
    if earlier_ledger.get('policy') != 'phase8_p2_opaque_decoder_evidence_v1':
        raise ValueError('Unrecognized DWG evidence ledger')
    if earlier_ledger.get('verdict') != 'PARTIAL_NO_GO' or earlier_ledger.get('quantity_approved') is not False:
        raise ValueError('Ledger contains unsafe acceptance')
    raw_items = earlier_ledger.get('objects')
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError('Empty original source object ledger')
    if not isinstance(earlier_ledger.get('opaque_object_count'), int) or len(raw_items) != earlier_ledger['opaque_object_count']:
        raise ValueError('Opaque roster count differs')

    dxf = ezdxf.readfile(converted_dxf)
    root_handle = earlier_ledger.get('named_root_handle')
    if (not isinstance(root_handle, str) or not root_handle.strip()
            or any(ch not in '0123456789ABCDEF' for ch in root_handle.strip().upper())):
        raise ValueError('Frozen source ledger must explicitly name the original root handle')
    named = dxf.entitydb.get(root_handle.strip().upper())
    if named is None or named.dxftype() != 'DICTIONARY':
        raise ValueError('Original named root 1A is not preserved')
    classes = {c.dxf.name: c for c in dxf.classes}
    observed = []
    used = set()
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError('Malformed opaque source item')
        handle = str(item.get('handle', '')).upper()
        name = str(item.get('class_name', ''))
        root = str(item.get('named_root', ''))
        if (not handle or handle in used or not isinstance(item.get('owner_path'), str)
                or item.get('decoder_object') != 'UNKNOWN_OBJ'
                or root not in {'Autodesk_MAP', 'AEC_VARS'}):
            raise ValueError('Malformed opaque source identity')
        used.add(handle)
        if name not in classes:
            raise ValueError(f'Original class lost from converted DXF CLASSES: {name}')
        cls = classes[name]
        if int(cls.dxf.get('is_an_entity', 1)) != 0:
            raise ValueError('Opaque class unexpectedly marked graphical in DXF')
        source_parent_chain = [h.strip().upper() for h in item['owner_path'].split('<-')]
        if (len(source_parent_chain) < 3 or source_parent_chain[0] != handle
                or source_parent_chain[-1] != str(named.dxf.handle).upper()):
            raise ValueError('Untrusted source ownership chain')
        named_parent = named.get(root)
        if (not named_parent or isinstance(named_parent, str) or
                source_parent_chain[-2] != str(named_parent.dxf.handle).upper()):
            raise ValueError('Source ownership contradicts converted root dictionary')
        entry = dxf.entitydb.get(handle)
        observed.append({
            'handle': handle, 'source_class': name, 'source_dictionary_root': root,
            'source_owner_path': item['owner_path'],
            'class_definition_preserved': True,
            'dxf_class_claimed_instance_count': int(cls.dxf.get('instance_count', -1)),
            'converted_object_present': entry is not None,
            'converted_object_type': entry.dxftype() if entry is not None else None,
            'source_payload_independently_verified': False,
        })
    direct_dangling = []
    for root_name in ('Autodesk_MAP', 'AEC_VARS'):
        try:
            root_dict = named.get(root_name)
        except Exception as exc:
            raise ValueError(f'Could not resolve {root_name} dictionary') from exc
        if root_dict is None or isinstance(root_dict, str) or root_dict.dxftype() != 'DICTIONARY':
            raise ValueError(f'Named source dictionary {root_name} is missing')
        for key, ref in root_dict.items():
            handle = _handle_of(ref)
            if handle in used and dxf.entitydb.get(handle) is None:
                direct_dangling.append({'named_root': root_name,
                                        'parent_dictionary_handle': root_dict.dxf.handle,
                                        'dictionary_key': key, 'missing_target_handle': handle})
    lost = [row for row in observed if not row['converted_object_present']]
    evidence = {
        'policy': 'phase8_p2_opaque_dxf_conversion_comparison_v1',
        'original_dwg_sha256': source_sha,
        'converted_dxf_sha256': dxf_sha,
        'dxf_version': dxf.dxfversion,
        'source_decoder': earlier_ledger.get('decoder_label'),
        'independent_decoder_executed': False,
        'source_opaque_count': len(observed),
        'dxf_missing_opaque_count': len(lost),
        'dxf_preserved_opaque_count': len(observed) - len(lost),
        'dxf_missing_opaque_handles': [row['handle'] for row in lost],
        'class_definitions_present': len(observed),
        'dangling_named_dictionary_references_count': len(direct_dangling),
        'dangling_named_dictionary_references': direct_dangling,
        'opaque_items': observed,
        'financial_takeoff_allowed': False,
        'quantity_approved': False,
        'verdict': 'PARTIAL_NO_GO',
        'limitation': 'Both LibreDWG JSON and DXF derive from the same decoder; these findings are not an independent native-oracle check.',
    }
    return evidence