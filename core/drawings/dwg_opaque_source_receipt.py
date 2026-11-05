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
        # AC1018 modular-short length prefix uses two bytes for lengths below
        # 32768 and four bytes from 32768 onward; the CRC takes two bytes.
        # This checks framing only, not the meaning of proprietary content.
        overhead = 4 if declared_size < 32768 else 6
        if len(encoded) != declared_size + overhead:
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
    unverified_count = dxf_link_report.get('unverified_target_count', 0)
    if type(unverified_count) is not int or unverified_count < 0:
        unverified_count = None
    if (type(count) is not int or count < 0 or unverified_count is None
            or not isinstance(report_state, str)):
        status = 'INDETERMINATE_DXF_DICTIONARY_GRAPH'
    elif report_state == 'BROKEN_DXF_DICTIONARY_LINKS' and count > 0:
        status = 'SOURCE_OPAQUE_RECORD_STREAMS_READ_DXF_LINKS_DANGLING'
    elif report_state == 'INDETERMINATE_DXF_DICTIONARY_TARGETS' and count == 0 and unverified_count > 0:
        status = 'SOURCE_OPAQUE_RECORD_STREAMS_READ_DXF_TARGETS_INDETERMINATE'
    elif count > 0 or report_state in {
            'BROKEN_DXF_DICTIONARY_LINKS', 'AMBIGUOUS_NAMED_DICTIONARY_ROOTS',
            'INDETERMINATE_DXF_DICTIONARY_TARGETS'}:
        status = 'INDETERMINATE_DXF_DICTIONARY_GRAPH'
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
        'converted_dxf_unverified_target_count':unverified_count,
        'converted_dxf_unverified_targets':dxf_link_report.get('unverified_target_references', []),
        'status':status, 'automatic_patch_authorized':False,
        'opaque_payload_semantics_verified':False,
        'full_source_graph_verified':False, 'financial_quantity_approved':False,
        'engineering_acceptance':'PARTIAL_NO_GO',
        'next_action':'Obtain vendor/ODA/custom-object-enabled re-export with byte-preserving source-vs-output proof; do not synthesize DXF entities from opaque bytes.',
    }



def summarize_converted_opaque_identity_coverage(source_records, converted_dxf_document):
    """Compare source-authenticated opaque record IDs with converted DXF identities.

    Matching an ID does NOT verify record bytes, class meaning, owners or links.
    Fail on duplicate/malformed source identities and expose aggregate counts
    only (never publish private handles, original bytes or source hashes).
    """
    if not isinstance(source_records, list) or not 1 <= len(source_records) <= MAX_OBJECTS:
        raise ValueError('Expected bounded authenticated opaque source records')
    if not hasattr(converted_dxf_document, 'entitydb'):
        raise ValueError('DXF document lacks an entity index')
    # A reused source handle can point to an ordinary LINE, DICTIONARY,
    # ACAD_PROXY_OBJECT, etc. in DXF. This is an identity collision, not an
    # original custom instance's successful semantic preservation.
    # This is an intentionally bounded denylist of *known* standard DXF types.
    # Unknown/custom types remain UNVERIFIED rather than presumed authentic.
    standard_dxf_types = frozenset((
        'LINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'POINT', 'SOLID',
        'TRACE', '3DFACE', 'POLYLINE', 'VERTEX', 'SEQEND', 'LWPOLYLINE',
        'HATCH', 'INSERT', 'ATTRIB', 'ATTDEF', 'DIMENSION', 'LEADER',
        'MLEADER', 'TEXT', 'MTEXT', 'XLINE', 'RAY', 'VIEWPORT',
        'BLOCK', 'ENDBLK', 'LAYER', 'STYLE', 'LTYPE', 'APPID', 'VPORT',
        'BLOCK_RECORD', 'LAYOUT', 'DICTIONARY', 'DICTIONARYVAR',
        'XRECORD', 'GROUP', 'MATERIAL', 'IMAGE', 'IMAGEDEF',
        'UNDERLAY', '3DSOLID', 'REGION', 'BODY', 'MESH',
    ))
    seen = set()
    present = 0
    reused_standard = 0
    replaced_proxy = 0
    present_custom_type_unverified = 0
    unreadable_type = 0
    for record in source_records:
        if not isinstance(record, dict):
            raise ValueError('Invalid authenticated opaque source item')
        handle = record.get('handle')
        if (not isinstance(handle, str) or not handle or len(handle) > 64
                or any(ch not in '0123456789abcdefABCDEF' for ch in handle)):
            raise ValueError('Malformed opaque source handle')
        number = int(handle, 16)
        if not 0 < number < 2**64:
            raise ValueError('Null or out-of-bounds opaque source identity')
        canonical = format(number, 'X')
        if canonical in seen:
            raise ValueError('Duplicate opaque source identity')
        seen.add(canonical)
        candidate = converted_dxf_document.entitydb.get(canonical)
        if candidate is None:
            continue
        present += 1
        try:
            reader = getattr(candidate, 'dxftype', None)
            type_name = reader() if callable(reader) else None
        except Exception:
            type_name = None
        if not isinstance(type_name, str) or not type_name:
            unreadable_type += 1
        elif type_name.upper() in ('ACAD_PROXY_OBJECT', 'ACAD_PROXY_ENTITY'):
            replaced_proxy += 1
        elif type_name.upper() in standard_dxf_types:
            reused_standard += 1
        else:
            present_custom_type_unverified += 1
    missing = len(seen) - present
    return {
        'source_opaque_identity_count': len(seen),
        'converted_dxf_identity_present_count': present,
        'converted_dxf_identity_missing_count': missing,
        'converted_dxf_identity_reused_as_standard_type_count': reused_standard,
        'converted_dxf_identity_replaced_by_proxy_count': replaced_proxy,
        'converted_dxf_identity_custom_type_unverified_count': present_custom_type_unverified,
        'converted_dxf_identity_type_unreadable_count': unreadable_type,
        'converted_dxf_opaque_identity_status': (
            'SOURCE_OPAQUE_OBJECT_IDENTITIES_MISSING_NO_GO' if missing
            else 'SOURCE_OPAQUE_IDENTITIES_REUSED_AS_STANDARD_NO_GO' if reused_standard
            else 'SOURCE_OPAQUE_IDENTITIES_REPLACED_BY_PROXY_NO_GO' if replaced_proxy
            else 'SOURCE_IDENTITIES_PRESENT_PAYLOAD_UNVERIFIED_NO_GO'
        ),
        'source_record_payload_semantics_verified': False,
        'converted_opaque_payload_bytes_independently_verified': False,
        'source_reference_graph_complete': False,
        'automatic_reconstruction_authorized': False,
        'financial_quantity_approved': False,
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
    # Authenticated raw source record identities must not silently disappear.
    # This is a separate observation from dictionary-link presence or CLI exit.
    decision.update(summarize_converted_opaque_identity_coverage(receipts, out))
    if hashlib.sha256(original.read_bytes()).hexdigest()!=sh0 or hashlib.sha256(converted.read_bytes()).hexdigest()!=shd0:
        raise ValueError('Source files changed during independent audit')
    return decision