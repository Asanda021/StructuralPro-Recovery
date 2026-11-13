"""Read-only independent native DWG/DXF coverage audit. NEVER grants quantities.

The high-level ezdwg modelspace iterator may include entities whose original
owner is a non-model BLOCK_RECORD. Do not call all such records dropped lines.
The source, not converted DXF, is the second decoder's input.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from importlib import metadata
from pathlib import Path
import math

from dataclasses import dataclass

LINE_COORDINATE_TOLERANCE = 1e-7

@dataclass(frozen=True)
class _RawLine:
    section: str
    block_handle: str
    block_record_handle: str
    owner_handle: str
    layer: str
    start: tuple[float, float, float]
    end: tuple[float, float, float]


def locate_raw_dxf_lines(dxf_path, handles):
    """Targeted read of raw DXF LINE records; preserve BLOCKS provenance."""
    found = {}
    if not handles:
        return found
    if len(handles)>1_000_000:
        raise ValueError('Unbounded raw DXF handles')
    section = ''; block_handle = ''; block_record = ''
    pending = None; fields = {}

    def close():
        nonlocal section, block_handle, block_record
        if pending == 'SECTION':
            section = fields.get('2','').upper()
        elif pending == 'ENDSEC':
            section = '';block_handle='';block_record=''
        elif pending == 'BLOCK' and section == 'BLOCKS':
            block_handle = fields.get('5','').upper()
            block_record = fields.get('330','').upper()
        elif pending == 'ENDBLK' and section == 'BLOCKS':
            block_handle='';block_record=''
        elif pending == 'LINE':
            try:
                handle = int(fields.get('5',''),16)
            except ValueError as exc:
                raise ValueError('Invalid raw DXF LINE handle') from exc
            if handle in handles:
                if handle in found:
                    raise ValueError('Duplicate raw DXF LINE handle')
                def pt(x,y,z):
                    vals = (float(fields[x]),float(fields[y]),float(fields.get(z,'0')))
                    if not all(math.isfinite(v) for v in vals):
                        raise ValueError('Nonfinite raw DXF LINE')
                    return vals
                found[handle] = _RawLine(
                    section,block_handle if section=='BLOCKS' else '',
                    block_record if section=='BLOCKS' else '',
                    fields.get('330','').upper(),fields.get('8',''),
                    pt('10','20','30'),pt('11','21','31'))

    with Path(dxf_path).open('rb') as stream:
        if stream.read(22).startswith(b'AutoCAD Binary DXF'):
            raise ValueError('Binary DXF requires separate parser')
        stream.seek(0)
        lines=0
        while True:
            raw_code = stream.readline()
            if not raw_code: break
            raw_value = stream.readline()
            if not raw_value: raise ValueError('Truncated DXF pair')
            lines+=1
            if lines>12_000_000: raise ValueError('Too many DXF pairs')
            code=raw_code.strip().decode('ascii','strict')
            if not code.isdecimal(): raise ValueError('Malformed DXF group code')
            value=raw_value.strip().decode('utf-8','replace')
            if code=='0':
                if pending is not None: close()
                pending=value.upper();fields={}
            elif pending is not None:
                fields[code]=value
        if pending is not None:close()
    return found


def compare_raw_and_native_line(raw, entity, source_layers):
    try:
        layer = source_layers[int(entity.dxf.get('layer_handle'))]
        a,b = _point3(entity.dxf.get('start')),_point3(entity.dxf.get('end'))
        return raw.layer == layer and all(
            math.isclose(x,y,rel_tol=0.0, abs_tol=LINE_COORDINATE_TOLERANCE)
            for p,q in ((a,raw.start),(b,raw.end)) for x,y in zip(p,q))
    except (ValueError,TypeError,KeyError,AttributeError):
        return False


PINNED_NATIVE_VERSION = "0.17.0"
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_DXF_BYTES = 250 * 1024 * 1024


def classify_missing_line(native_owner, model_record, raw, geometry_and_layer_match):
    """Classify a missing LINE without converting BLOCK definitions into quantities.

    Verified BLOCK provenance is *only* a location classification, never
    proof that INSERT/DIMENSION uses the block or that geometry is payable.
    """
    if raw is None:
        return "ABSENT_FROM_RAW_DXF"
    if not geometry_and_layer_match:
        return "RAW_DXF_GEOMETRY_OR_LAYER_MISMATCH"
    if native_owner is None or model_record is None:
        return "NATIVE_OWNERSHIP_UNVERIFIED"
    if int(native_owner) == int(model_record):
        return "DIRECT_MODELSPACE_MISSING_FROM_PARSED_DXF"
    if (raw.section == 'BLOCKS' and raw.block_handle
            and raw.block_record_handle
            and raw.owner_handle.upper() == raw.block_record_handle.upper()
            and int(raw.owner_handle, 16) == int(native_owner)):
        return "MATCHED_BLOCK_DEFINITION_NOT_DIRECT_MODELSPACE"
    return "MODELSPACE_OR_BLOCK_OWNERSHIP_CONFLICT"


def _point3(v):
    vals = tuple(float(x) for x in v)
    if len(vals) not in (2, 3) or not all(math.isfinite(x) for x in vals):
        raise ValueError('Invalid LINE coordinate')
    return vals if len(vals) == 3 else (*vals, 0.0)


def _line_equal(native, converted, native_layer):
    if native_layer != str(converted.dxf.layer):
        return False
    if int(native.dxf.get('invisible', 0) or 0) != int(converted.dxf.get('invisible', 0) or 0):
        return False
    for name in ('start', 'end'):
        a, b = _point3(native.dxf.get(name)), _point3(converted.dxf.get(name))
        if any(not math.isclose(x, y, rel_tol=0.0, abs_tol=LINE_COORDINATE_TOLERANCE) for x, y in zip(a, b)):
            return False
    return True


def _bounded_sha(path, maximum, suffix):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() != suffix or not (6 <= p.stat().st_size <= maximum):
        raise ValueError(f'Invalid {suffix} source path or size')
    with p.open('rb') as stream:
        return sha256(stream.read()).hexdigest()


def audit_native_to_dxf(original_dwg, converted_dxf, *, expected_dwg_sha256, expected_dxf_sha256):
    """Return an evidence receipt with enforced PARTIAL_NO_GO, no model mutation.

    The independent reader is *optional and pinned*. Failure never falls back
    to the LibreDWG DXF as its native source.
    """
    dwg = Path(original_dwg); dxf = Path(converted_dxf)
    dwg_sha = _bounded_sha(dwg, MAX_SOURCE_BYTES, '.dwg')
    dxf_sha = _bounded_sha(dxf, MAX_DXF_BYTES, '.dxf')
    if dwg_sha != expected_dwg_sha256 or dxf_sha != expected_dxf_sha256:
        raise ValueError('Source hash mismatch: abort independent comparison')
    with dwg.open('rb') as fh:
        signature = fh.read(6).decode('ascii', errors='replace')
    if signature not in ('AC1018',):
        raise ValueError('Unexpected native DWG signature for this evidence contract')
    try:
        installed_version = metadata.version('ezdwg')
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError('Pinned native decoder ezdwg not installed: NO-GO') from exc
    if installed_version != PINNED_NATIVE_VERSION:
        raise RuntimeError('Pinned independent reader version mismatch: NO-GO')
    import ezdwg
    import ezdxf
    source_stat_before = (dwg.stat().st_size, dwg.stat().st_mtime_ns)
    dxf_stat_before = (dxf.stat().st_size, dxf.stat().st_mtime_ns)
    native = ezdwg.read(str(dwg))
    converted = ezdxf.readfile(str(dxf))
    if native.version != signature:
        raise ValueError('Reader decoded a different DWG version')
    native_map, target_map = {}, {}
    native_type_counts, converted_type_counts = Counter(), Counter()
    for entity in native.modelspace().iter_entities():
        h = int(entity.handle); typ = str(entity.dxftype)
        if h in native_map or len(native_map) >= 1_000_000:
            raise ValueError('Duplicate or unbounded native entity handles')
        native_map[h] = (typ, entity)
        native_type_counts[typ] += 1
    for entity in converted.modelspace():
        h = int(entity.dxf.handle, 16); typ = entity.dxftype()
        if h in target_map or len(target_map) >= 1_000_000:
            raise ValueError('Duplicate or unbounded DXF modelspace handles')
        target_map[h] = (typ, entity)
        converted_type_counts[typ] += 1
    missing = sorted(set((k,t) for k,(t,e) in native_map.items())
                     - set((k,t) for k,(t,e) in target_map.items()))
    extra = sorted(set((k,t) for k,(t,e) in target_map.items())
                   - set((k,t) for k,(t,e) in native_map.items()))
    native_layers = {int(layer.handle):str(layer.name) for layer in native.layers}
    model_record = int(native.layouts()['Model']['block_record_handle'])
    ownership_issues = Counter()
    dxf_model_record = int(converted.modelspace().block_record.dxf.handle, 16)
    mismatch_handles = []
    common_line_count = 0
    for handle, (typ, entity) in native_map.items():
        other = target_map.get(handle)
        if typ == 'LINE' and other is not None and other[0] == 'LINE':
            common_line_count += 1
            native_owner = entity.dxf.get('owner_handle')
            if not native_owner:
                ownership_issues['NATIVE_OWNER_UNVERIFIED'] += 1
            elif int(native_owner) != model_record:
                ownership_issues['NATIVE_OWNER_OUTSIDE_MODELSPACE'] += 1
            if other[1].dxf.owner != format(dxf_model_record, 'X'):
                ownership_issues['DXF_OWNER_OUTSIDE_MODELSPACE'] += 1
            layer_handle = entity.dxf.get('layer_handle')
            layer = native_layers.get(int(layer_handle)) if layer_handle is not None else None
            try:
                matching = _line_equal(entity, other[1], layer)
            except (TypeError, ValueError, KeyError):
                matching = False
            if not matching:
                mismatch_handles.append(format(handle,'X'))
    missing_lines = {h for h, typ in missing if typ == 'LINE'}
    provenance = locate_raw_dxf_lines(dxf, missing_lines)
    categorized = []
    for handle,typ in missing:
        native_entity = native_map[handle][1]
        if typ == 'LINE':
            raw = provenance.get(handle)
            matched = bool(raw and compare_raw_and_native_line(raw, native_entity, native_layers))
            owner = native_entity.dxf.get('owner_handle')
            category = classify_missing_line(owner, model_record, raw, matched)
            categorized.append({'handle':format(handle,'X'), 'type':typ, 'native_owner':format(int(owner),'X') if owner is not None else None,
                                'dxf_raw_section':raw.section if raw else None,
                                'dxf_block_handle':raw.block_handle if raw else None,
                                'dxf_block_record':raw.block_record_handle if raw else None,
                                'dxf_raw_geometry_layer_match':matched, 'classification':category})
        else:
            categorized.append({'handle':format(handle,'X'), 'type':typ, 'classification':'UNSUPPORTED_SOURCE_TYPE_MISSING'})
    if _bounded_sha(dwg, MAX_SOURCE_BYTES, '.dwg') != dwg_sha or _bounded_sha(dxf, MAX_DXF_BYTES, '.dxf') != dxf_sha:
        raise ValueError('Source bytes changed during audit')
    if (dwg.stat().st_size,dwg.stat().st_mtime_ns) != source_stat_before or (dxf.stat().st_size,dxf.stat().st_mtime_ns) != dxf_stat_before:
        raise ValueError('Source metadata changed during audit')
    return {
        'policy':'structuralpro_p8p2_native_dxf_crosscheck_v1',
        'status':'PARTIAL_NO_GO', 'independent_native_reader_executed':True,
        'native_decoder':'ezdwg', 'native_decoder_version':installed_version,
        'original_dwg_sha256':dwg_sha, 'converted_dxf_sha256':dxf_sha,
        'native_units':native.units, 'dxf_insunits':int(converted.header.get('$INSUNITS',0) or 0),
        'native_modelspace_layout_record':format(model_record,'X'),
        'native_modelspace_iterator_count':len(native_map),
        'dxf_modelspace_iterator_count':len(target_map),
        'native_by_type':dict(sorted(native_type_counts.items())),
        'dxf_by_type':dict(sorted(converted_type_counts.items())),
        'missing_native_entries':categorized,
        'extra_dxf_entries':[[format(h,'X'), typ] for h,typ in extra],
        'shared_line_geometry_layer_mismatch_count':len(mismatch_handles),
        'shared_line_geometry_layer_mismatch_examples':mismatch_handles[:25],
        'shared_line_count':common_line_count,
        'shared_line_modelspace_ownership_issues':dict(sorted(ownership_issues.items())),
        'opaque_class_payloads_verified':False,
        'source_drawing_revision_verified':False,
        'financial_geometry_approved':False,
        'approved_quantities':0,
        'note':'Native roster vs DXF location is not opaque-class coverage; classification of BLOCK members does not certify INSERT/reference reachability.'
    }