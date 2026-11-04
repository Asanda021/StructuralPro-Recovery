"""Read-only diagnostic of opaque LibreDWG objects, never quantity authority.

This checks internal consistency of a previously produced LibreDWG JSON snapshot
against a separately recorded C-API status receipt and original DWG SHA-256.
A matching class/owner graph is NOT an independent decoder or geometry check.
The tool never returns an approval or alters an imported drawing.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

# Only decoding status bits previously recorded by the external C-API audit.
_KNOWN_ERROR_BITS = {4: 'DWG_ERR_UNHANDLEDCLASS', 64: 'DWG_ERR_VALUEOUTOFBOUNDS'}
_EXPECTED_ROOTS = {'Autodesk_MAP', 'AEC_VARS'}
# Known opaque object categories from the currently audited drawing. New
# classes cannot be silently characterized as non-graphical by this auditor.
_EXPECTED_CLASS_ROOT = {
    'DMMAPMANAGER': 'Autodesk_MAP',
    'DMSTYLELIBRARY': 'Autodesk_MAP',
    'DMMAP': 'Autodesk_MAP',
    'DMBASEELEMENT': 'Autodesk_MAP',
    'DMDEFAULTSTYLE': 'Autodesk_MAP',
    'DMSTYLEREFERENCE': 'Autodesk_MAP',
    'DMSTYLECATEGORY': 'Autodesk_MAP',
    'AEC_VARS_DWG_SETUP': 'AEC_VARS',
}
_MAX_DWG_BYTES = 50 * 1024 * 1024


def _handle(value: Any) -> str:
    """Return canonical handle from LibreDWG's resolved reference array."""
    if (not isinstance(value, list) or len(value) < 3
            or type(value[-1]) is not int or value[-1] < 0):
        raise ValueError('Invalid resolved DWG handle')
    return f'{value[-1]:X}'


def _index_objects(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    objects = snapshot.get('OBJECTS')
    if not isinstance(objects, list) or not 0 < len(objects) <= 1_000_000:
        raise ValueError('Missing or oversized LibreDWG object roster')
    index = {}
    for obj in objects:
        if not isinstance(obj, dict):
            raise ValueError('Non-object in decoder roster')
        h = _handle(obj.get('handle'))
        if h in index:
            raise ValueError('Repeated decoded DWG object handle')
        index[h] = obj
    return index


def _parent_path(index: Mapping[str, Mapping[str, Any]], leaf: str) -> list[str]:
    path = [leaf]
    for _ in range(40):
        obj = index.get(path[-1])
        if obj is None:
            raise ValueError('Unresolved owner in decoded graph')
        parent = _handle(obj.get('ownerhandle'))
        if parent == '0':
            return path
        if parent in path:
            raise ValueError('Cyclic decoded ownership')
        path.append(parent)
    raise ValueError('Decoded ownership chain depth exceeded')


def audit_unknown_objects(source_dwg: str | Path, snapshot: Mapping[str, Any],
                          receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Audit a private decoder snapshot, returning a permanent *NO-GO* ledger.

    No C API is re-executed here. Error bitmask is treated as historical evidence
    supplied by the receipt and cannot be inferred from CLI ``SUCCESS``.
    """
    source = Path(source_dwg)
    if (not source.is_file() or source.suffix.casefold() != '.dwg'
            or not 6 < source.stat().st_size <= _MAX_DWG_BYTES):
        raise ValueError('Missing or oversized original DWG')
    digest = sha256(source.read_bytes()).hexdigest()
    if receipt.get('source_sha256') != digest:
        raise ValueError('Receipt source SHA-256 differs from original DWG')
    if snapshot.get('created_by', '').split()[0] != 'LibreDWG':
        raise ValueError('Diagnostic JSON has no LibreDWG origin label')
    obj_index = _index_objects(snapshot)
    raw_class_registry = snapshot.get('CLASSES')
    if not isinstance(raw_class_registry, list):
        raise ValueError('Missing DWG class table')
    registry = {}
    for cls in raw_class_registry:
        if not isinstance(cls, dict) or type(cls.get('number')) is not int:
            raise ValueError('Invalid class registry entry')
        if cls['number'] in registry:
            raise ValueError('Repeated custom class identifier')
        registry[cls['number']] = cls
    root_handle = '1A'
    root = obj_index.get(root_handle)
    if not root or root.get('object') != 'DICTIONARY':
        raise ValueError('Named root dictionary not found in decoded roster')
    root_items = root.get('items')
    if not isinstance(root_items, dict):
        raise ValueError('Root dictionary items absent')
    roots = {}
    for name in _EXPECTED_ROOTS:
        roots[name] = _handle(root_items.get(name))
        named = obj_index.get(roots[name])
        if not named or named.get('object') != 'DICTIONARY':
            raise ValueError('Named object dictionary missing')
    undecoded = [obj for obj in obj_index.values() if obj.get('object') in {'UNKNOWN_OBJ', 'UNKNOWN_ENT'}]
    expected = receipt.get('unknown_objects')
    if not isinstance(expected, list) or len(expected) < 1:
        raise ValueError('Decoder receipt lacks unknown object manifest')
    declared = {}
    for item in expected:
        if not isinstance(item, dict) or not isinstance(item.get('handle'), str):
            raise ValueError('Malformed unknown-object manifest')
        handle = item['handle'].upper()
        if handle in declared or type(item.get('type_code')) is not int:
            raise ValueError('Duplicate or invalid unknown manifest entry')
        declared[handle] = item
    seen = {}
    rows = []
    for obj in undecoded:
        handle = _handle(obj['handle'])
        item = declared.get(handle)
        if item is None or type(obj.get('type')) is not int or obj['type'] != item['type_code']:
            raise ValueError('Undeclared or mismatched opaque DWG object')
        class_info = registry.get(obj['type'])
        if not class_info or class_info.get('dxfname') != item.get('class'):
            raise ValueError('Opaque decoder class table disagrees with receipt')
        path = _parent_path(obj_index, handle)
        matched_roots = [k for k,v in roots.items() if v in path]
        if (len(matched_roots) != 1 or root_handle not in path
                or matched_roots[0] != _EXPECTED_CLASS_ROOT.get(class_info['dxfname'])):
            raise ValueError('Opaque owner does not resolve to the permitted named root')
        # An opaque object tagged as an entity is *not* safe to present as
        # a non-geometric dictionary entry. Never approve it or quantities.
        if obj.get('object') != 'UNKNOWN_OBJ':
            raise ValueError('Opaque graphical entity detected')
        seen[handle] = obj['type']
        rows.append({'handle': handle, 'class_code': obj['type'],
                     'class_name': class_info['dxfname'], 'decoder_object': obj['object'],
                     'named_root': matched_roots[0], 'owner_path': ' <- '.join(path),
                     'payload_decoded': False, 'geometry_authorized': False})
    if set(seen) != set(declared):
        raise ValueError('Unknown object set differs from independent audit manifest')
    if receipt.get('objects') != len(obj_index):
        raise ValueError('Receipt roster count mismatch')
    mask = receipt.get('libredwg_api_status')
    if type(mask) is not int or mask < 0:
        raise ValueError('C-API decoder status is not a valid integer')
    flags = [name for bit,name in _KNOWN_ERROR_BITS.items() if mask & bit]
    unclassified_bits = mask & ~sum(_KNOWN_ERROR_BITS)
    if sorted(flags) != sorted(receipt.get('libredwg_api_status_flags', [])):
        raise ValueError('Decoder status flags contradict recorded bitmask')
    # Textual CLI SUCCESS is not the actual C API decode status.
    return {
        'policy': 'phase8_p2_opaque_decoder_evidence_v1',
        'source_sha256': digest,
        'decoder_label': snapshot['created_by'],
        'decoder_status_from_prior_c_api_receipt': mask,
        'known_status_flags': flags,
        'additional_unclassified_status_bits': unclassified_bits,
        'cli_exit_from_prior_receipt': receipt.get('cli_exit'),
        'cli_message_from_prior_receipt': receipt.get('cli_stderr'),
        'decoded_object_count': len(obj_index),
        'opaque_object_count': len(rows),
        'opaque_by_named_dictionary': dict(Counter(r['named_root'] for r in rows)),
        'objects': sorted(rows, key=lambda r: int(r['handle'], 16)),
        'decoded_owner_graph_consistent': True,
        'full_decoder_object_graph_verified': False,
        'opaque_payloads_decoded': False,
        'source_dwg_revision_accepted': False,
        'quantity_approved': False,
        'financial_takeoff_allowed': False,
        'verdict': 'PARTIAL_NO_GO',
        'explanation': 'Consistency of one impaired decoder snapshot is not independent original-DWG fidelity.',
    }