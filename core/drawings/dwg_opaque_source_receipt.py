"""Read-only, SHA-bound source byte receipts for proprietary DWG objects.

A pinned independent raw decoder may read opaque bytes, but decoding bytes is
NOT understanding proprietary MAP/AEC object payload structure. Never emit the
payload, modify a drawing, infer units, repair missing DXF objects or approve
quantity based on this receipt.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from importlib import metadata

PINNED_READER = '0.17.0'
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_DXF_BYTES = 300 * 1024 * 1024
MAX_OBJECTS = 64
MAX_OBJECT_MAP_ENTRIES = 1_000_000


def _handles(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= MAX_OBJECTS:
        raise ValueError('Need 1..64 explicit source handles')
    output = []
    seen = set()
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError('Invalid DWG handle type')
        if isinstance(value, str):
            val = value.strip()
            if not val or any(c not in '0123456789abcdefABCDEF' for c in val):
                raise ValueError('Invalid DWG hex handle')
            number = int(val, 16)
        else:
            number = value
        if not 0 < number < 2**64 or number in seen:
            raise ValueError('Duplicate or out-of-bounds handle')
        seen.add(number)
        output.append(number)
    return output


def validate_object_map_entries(entries, expected_handles):
    """Veto duplicate/missing handles in the *exposed* native object-map index.

    This is a second consistency check against upstream record selection, NOT
    proof that a closed-source/compressed decoder exposes every corrupt entry.
    """
    required = set(_handles(expected_handles))
    seen = {}
    count = 0
    for row in entries:
        count += 1
        if count > MAX_OBJECT_MAP_ENTRIES:
            raise ValueError('Native DWG object map exceeds safe cap')
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            raise ValueError('Unexpected DWG object-map record')
        handle, offset = row
        if (type(handle) is not int or type(offset) is not int
                or not 0 < handle < 2**64 or offset < 0):
            raise ValueError('Invalid DWG index handle or offset')
        if handle in seen:
            raise ValueError('Duplicate native DWG object-map handle')
        seen[handle] = offset
    if not required.issubset(seen):
        raise ValueError('Target proprietary handle absent from independent object map')
    return {h: seen[h] for h in required}


def summarize_raw_records(raw_records, expected_handles):
    """Validate exactly one bounded independent raw record per claimed handle.

    Official ezdwg raw API returns (handle, offset, declared_size, type_code,
    list_of_bytes). The byte stream can include header/padding, so it is only
    labelled a raw-record stream, not a decoded proprietary payload.
    """
    required = set(_handles(expected_handles))
    seen = set()
    out = []
    for row in raw_records:
        if not isinstance(row, (list, tuple)) or len(row) != 5:
            raise ValueError('Unexpected independent decoder raw record schema')
        handle, offset, declared_size, type_code, data = row
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (handle, offset, declared_size, type_code)):
            raise ValueError('Invalid native object record metadata')
        if handle not in required or handle in seen or not 0 <= offset or not 0 < declared_size <= 8_000_000 or not 0 < type_code <= 65535:
            raise ValueError('Unknown, duplicate, or invalid native object record')
        if not isinstance(data, (list, tuple, bytes, bytearray)) or not 0 < len(data) <= 8_000_000:
            raise ValueError('Native record missing bounded byte stream')
        if any(not isinstance(b, int) or isinstance(b, bool) or not 0 <= b <= 255 for b in data):
            raise ValueError('Invalid native object byte stream')
        encoded = bytes(data)
        # Tested AC1018 native-record framing: the pinned ezdwg API returns
        # declared_size bytes plus four prefix/trailer bytes.  Eight original
        # private records exhibit this relation.  Other DWG versions are NOT
        # authorized by this narrow contract.
        if len(encoded) != declared_size + 4:
            raise ValueError('AC1018 native raw-record declared size mismatch')
        seen.add(handle)
        out.append({'handle':format(handle, 'X'), 'raw_record_sha256':hashlib.sha256(encoded).hexdigest(),
                    'raw_record_stream_bytes':len(encoded), 'record_declared_size':declared_size,
                    'native_type_code':type_code, 'native_object_offset':offset,
                    'proprietary_payload_semantics_verified':False})
    if seen != required:
        raise ValueError('Native reader omitted required source object records')
    return sorted(out, key=lambda v:int(v['handle'],16))


def opaque_recovery_decision(source_records, dxf_link_report, *, expected_source_sha256, converted_dxf_sha256):
    """No automatic repair, even when every source record is accessible.

    A dangling link is a verifiable inconsistency in the converted DXF; a
    source byte hash is NOT a convertible DXF entity or proprietary codec.
    """
    if not isinstance(source_records, list) or not source_records:
        raise ValueError('Missing authenticated source record receipts')
    if not isinstance(dxf_link_report, dict) or dxf_link_report.get('policy') != 'p8p2_dxf_named_dictionary_links_v1':
        raise ValueError('Missing verified converted DXF dictionary report')
    if dxf_link_report.get('financial_quantity_approved') is not False:
        raise ValueError('Untrusted dictionary report claims quantity approval')
    report_state = dxf_link_report.get('converted_dxf_namespace_integrity_status')
    count = dxf_link_report.get('dangling_or_invalid_count')
    if count is None or type(count) is not int or count < 0:
        status = 'INDETERMINATE_DXF_DICTIONARY_GRAPH'
    elif count > 0:
        status = 'SOURCE_OPAQUE_RECORD_STREAMS_READ_DXF_LINKS_DANGLING'
    else:
        status = 'SOURCE_OPAQUE_RECORD_STREAMS_READ_DXF_LINKS_NOT_PROVEN_COMPLETE'
    if not isinstance(expected_source_sha256,str) or len(expected_source_sha256)!=64 or not isinstance(converted_dxf_sha256,str) or len(converted_dxf_sha256)!=64:
        raise ValueError('SHA digests required')
    return {
        'policy':'p8p2_opaque_source_bytes_no_repair_v1',
        'source_dwg_sha256':expected_source_sha256, 'converted_dxf_sha256':converted_dxf_sha256,
        'source_record_count':len(source_records), 'records':source_records,
        'converted_dxf_named_dictionary_integrity_status':report_state,
        'converted_dxf_dangling_ref_count':count,
        'converted_dxf_dangling_refs':dxf_link_report.get('dangling_or_invalid_references', []),
        'status':status, 'automatic_patch_authorized':False,
        'opaque_payload_semantics_verified':False,
        'full_source_graph_verified':False, 'financial_quantity_approved':False,
        'engineering_acceptance':'PARTIAL_NO_GO',
        'next_action':'Obtain vendor/ODA/custom-object-enabled re-export with byte-preserving source-vs-output proof; do not synthesize DXF entities from opaque bytes.',
    }


def audit_original_opaque_records(source_dwg, converted_dxf, claimed_handles, *, expected_original_sha256):
    """Read original DWG raw records with ezdwg v0.17.0 and compare DXF links.

    Requires source access; never writes or transmits source bytes. Public code
    has no original source identifiers and cannot self-authorize engineering.
    """
    import ezdxf
    from core.drawings.dwg_source_display_integrity import audit_named_dictionary_links
    original, converted = Path(source_dwg), Path(converted_dxf)
    required = _handles(claimed_handles)
    if (not original.is_file() or original.suffix.lower()!='.dwg'
            or not 6 < original.stat().st_size <= MAX_SOURCE_BYTES):
        raise ValueError('Original DWG missing or outside size limit')
    if (not converted.is_file() or converted.suffix.lower()!='.dxf'
            or not 10 < converted.stat().st_size <= MAX_DXF_BYTES):
        raise ValueError('Converted DXF missing or outside size limit')
    original_bytes = original.read_bytes()
    sh0=hashlib.sha256(original_bytes).hexdigest()
    shd0=hashlib.sha256(converted.read_bytes()).hexdigest()
    if original_bytes[:6] != b'AC1018':
        raise ValueError('Raw-record framing is validated only for AC1018 DWG')
    if sh0!=expected_original_sha256:
        raise ValueError('Original DWG SHA does not match frozen evidence')
    if metadata.version('ezdwg')!=PINNED_READER:
        raise ValueError('Independent ezdwg version not pinned')
    import ezdwg
    index_rows = ezdwg.raw.list_object_map_entries(
        str(original), limit=MAX_OBJECT_MAP_ENTRIES + 1)
    target_offsets = validate_object_map_entries(index_rows, required)
    raw_records=ezdwg.raw.read_object_records_by_handle(str(original),required,limit=MAX_OBJECTS)
    receipts=summarize_raw_records(raw_records,required)
    for item in receipts:
        handle = int(item['handle'], 16)
        if item['native_object_offset'] != target_offsets[handle]:
            raise ValueError('Native raw record disagrees with object-map offset')
    out=ezdxf.readfile(converted)
    integrity=audit_named_dictionary_links(out)
    decision=opaque_recovery_decision(receipts,integrity,
                                      expected_source_sha256=sh0,converted_dxf_sha256=shd0)
    if hashlib.sha256(original.read_bytes()).hexdigest()!=sh0 or hashlib.sha256(converted.read_bytes()).hexdigest()!=shd0:
        raise ValueError('Source files changed during independent audit')
    return decision