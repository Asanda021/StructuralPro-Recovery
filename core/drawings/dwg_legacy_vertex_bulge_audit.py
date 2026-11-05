"""Read-only AC1032 legacy VERTEX bulge comparison between two diagnostic DXFs.

Neither DXF is an original-DWG geometry oracle. A matching field subset does not
establish AEC semantics, SHX interpretation, units or payable takeoff authority.
Return only bounded aggregate counts, never private handles or coordinates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import math
from pathlib import Path
import re

_MAX_VERTICES = 1_000_000
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def _snapshot(path: str | Path, expected_digest: str) -> tuple[Path, tuple]:
    if not isinstance(expected_digest, str) or _SHA256.fullmatch(expected_digest) is None:
        raise ValueError("Missing pinned SHA-256 for private source or DXF")
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Private audit input must be a regular, non-symlink file")
    stat = p.stat()
    identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    with p.open("rb") as f:
        measured = hashlib.file_digest(f, "sha256").hexdigest()
    if measured.casefold() != expected_digest.casefold():
        raise ValueError("Private audit input SHA-256 does not match frozen evidence")
    return p, identity


def _unchanged(p: Path, identity: tuple, expected_digest: str) -> None:
    if p.is_symlink() or not p.is_file():
        raise ValueError("Private input was replaced during audit")
    stat = p.stat()
    if (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) != identity:
        raise ValueError("Private audit input changed during read")
    with p.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest().casefold() != expected_digest.casefold():
            raise ValueError("Private audit input bytes changed during read")


def _handle(value: object) -> str:
    if not isinstance(value, str) or not value or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("Invalid VERTEX/parent identity")
    n = int(value, 16)
    if n <= 0 or n >= 2**64:
        raise ValueError("Null or oversized VERTEX/parent identity")
    return format(n, "X")


def _raw_vertex_owner_bulge(path: Path) -> tuple[dict[str, tuple[str, float]], dict[str, int]]:
    """Inspect original text-DXF tags before ezdxf repairs owner sequences.

    This is deliberately strict and bounded: malformed or unsupported raw
    VERTEX records are blockers rather than candidates for silent repair.
    """
    values = {}
    parent_flags = {}
    kind = None
    fields = {}

    def flush():
        if kind == b"VERTEX":
            if not {5, 330}.issubset(fields):
                raise ValueError("Original DXF VERTEX lacks unique raw identity/owner/bulge tags")
            handle, owner, bulge = fields[5], fields[330], fields.get(42, 0.0)
            if handle in values or len(values) >= _MAX_VERTICES:
                raise ValueError("Duplicate or unbounded raw DXF VERTEX")
            values[handle] = (owner, bulge)
        elif kind == b"POLYLINE":
            if 5 not in fields:
                raise ValueError("Original DXF POLYLINE lacks raw identity")
            handle = fields[5]
            if handle in parent_flags or len(parent_flags) >= _MAX_VERTICES:
                raise ValueError("Duplicate or unbounded raw DXF POLYLINE")
            parent_flags[handle] = fields.get(70, 0)

    with path.open('rb') as stream:
        if stream.read(18).startswith(b'AutoCAD Binary DXF'):
            raise ValueError("Binary DXF unsupported by raw VERTEX evidence checker")
        stream.seek(0)
        while True:
            code_line = stream.readline(65537)
            if not code_line:
                break
            val_line = stream.readline(65537)
            if not val_line or len(code_line) > 65536 or len(val_line) > 65536:
                raise ValueError("Malformed or unbounded DXF group pair")
            try:
                code = int(code_line.strip())
            except ValueError as exc:
                raise ValueError("Malformed DXF group code") from exc
            value = val_line.strip()
            if code == 0:
                flush()
                kind, fields = value, {}
            elif (kind == b'VERTEX' and code in (5, 330, 42)) or (kind == b'POLYLINE' and code in (5, 70)):
                if code in fields:
                    raise ValueError("Duplicated raw DXF " + ("VERTEX" if kind == b"VERTEX" else "POLYLINE") + " tag")
                if code in (5, 330):
                    try:
                        fields[code] = _handle(value.decode('ascii'))
                    except UnicodeError as exc:
                        raise ValueError("Non-ASCII raw DXF entity handle") from exc
                elif code == 70:
                    try:
                        flags = int(value.decode('ascii'))
                    except (ValueError, UnicodeError) as exc:
                        raise ValueError("Malformed raw POLYLINE flags") from exc
                    if not 0 <= flags <= 65535:
                        raise ValueError("Out-of-bounds raw POLYLINE flags")
                    fields[70] = flags
                else:
                    try:
                        number = float(value.decode('ascii'))
                    except (ValueError, UnicodeError) as exc:
                        raise ValueError("Malformed raw DXF VERTEX bulge") from exc
                    if not math.isfinite(number):
                        raise ValueError("Nonfinite raw DXF VERTEX bulge")
                    fields[42] = number
        flush()
    return values, parent_flags


def _roster(doc) -> dict[str, tuple]:
    """Capture unique legacy VERTEX identities with parent and numeric fields."""
    roster = {}
    model_record = _handle(str(doc.modelspace().block_record_handle))
    for entity in doc.entitydb.values():
        if entity is None or entity.dxftype() != "VERTEX":
            continue
        if len(roster) >= _MAX_VERTICES:
            raise ValueError("Legacy vertex audit exceeds safe record bound")
        h = _handle(entity.dxf.handle)
        parent = _handle(entity.dxf.get("owner"))
        parent_entity = doc.entitydb.get(parent)
        if parent_entity is None or parent_entity.dxftype() != "POLYLINE":
            raise ValueError("Legacy VERTEX is not owned by a POLYLINE")
        parent_record = _handle(parent_entity.dxf.get("owner"))
        group = "ENTITIES" if parent_record == model_record else "BLOCKS_OR_OTHER"
        pt = entity.dxf.get("location")
        if pt is None:
            raise ValueError("Legacy VERTEX position unavailable")
        xyz = tuple(float(v) for v in pt)
        bulge = float(entity.dxf.get("bulge", 0.0))
        flag = entity.dxf.get("flags", 0)
        if len(xyz) != 3 or not all(math.isfinite(v) for v in (*xyz, bulge)):
            raise ValueError("Nonfinite VERTEX geometry or bulge")
        if type(flag) is not int or flag < 0:
            raise ValueError("Malformed VERTEX role flags")
        if h in roster:
            raise ValueError("Duplicate legacy VERTEX handle")
        roster[h] = (parent, parent_record, group, xyz, bulge, flag)
    return roster


def audit_ac1032_legacy_vertex_bulge_parity(
    original_dwg: str | Path,
    reference_dxf: str | Path,
    candidate_dxf: str | Path,
    *,
    original_sha256: str,
    reference_sha256: str,
    candidate_sha256: str,
    abs_tolerance: float = 1e-9,
) -> dict:
    """Pin all three files and detect a false-straight legacy POLYLINE.

    Two decoder outputs can corroborate or contradict each other; neither
    establishes the original source's actual bulge truth. No file is modified.
    """
    if type(abs_tolerance) is not float or not 0 < abs_tolerance <= 1e-6:
        raise ValueError("Unbounded or invalid numeric tolerance")
    paths = (original_dwg, reference_dxf, candidate_dxf)
    digests = (original_sha256, reference_sha256, candidate_sha256)
    captures = [_snapshot(p, sha) for p, sha in zip(paths, digests)]
    if (len({str(p.resolve()) for p, _ in captures}) != 3
            or len({(identity[0], identity[1]) for _, identity in captures}) != 3):
        raise ValueError("Three independent input files are required")
    original = captures[0][0]
    with original.open("rb") as stream:
        if stream.read(6) != b"AC1032":
            raise ValueError("This scope audits original AC1032 DWG only")
    # Verify raw tags first, before a third-party parser can normalize bad
    # values, hide duplicate tags or reject nonfinite inputs in another way.
    raw_reference, raw_ref_parent_flags = _raw_vertex_owner_bulge(captures[1][0])
    raw_candidate, raw_cand_parent_flags = _raw_vertex_owner_bulge(captures[2][0])
    import ezdxf
    ref = ezdxf.readfile(str(captures[1][0]))
    candidate = ezdxf.readfile(str(captures[2][0]))
    rr, cr = _roster(ref), _roster(candidate)
    # Some readers silently reset group-330 when reconstructing POLYLINE
    # sequences; this must not be mistaken for verified original ownership.
    for raw_roster, roster in ((raw_reference, rr), (raw_candidate, cr)):
        if set(raw_roster) != set(roster):
            raise ValueError("Parsed DXF VERTEX roster differs from raw tags")
        for h, record in roster.items():
            raw_owner, raw_bulge = raw_roster[h]
            if raw_owner != record[0] or abs(raw_bulge - record[4]) > abs_tolerance:
                raise ValueError("Parsed DXF VERTEX ownership/bulge differs from raw tags")
    if not rr:
        raise ValueError("Reference DXF has no legacy VERTEX records")

    def parsed_parent_flags(doc, roster, raw_flags):
        result = {}
        for parent in {entry[0] for entry in roster.values()}:
            record = doc.entitydb.get(parent)
            if record is None or record.dxftype() != "POLYLINE":
                raise ValueError("Legacy vertex parent POLYLINE missing")
            flags = record.dxf.get("flags", 0)
            if type(flags) is not int or not 0 <= flags <= 65535:
                raise ValueError("Invalid parsed POLYLINE flags")
            if parent not in raw_flags or flags != raw_flags[parent]:
                raise ValueError("Parsed POLYLINE flags differ from raw DXF")
            result[parent] = flags
        return result

    reference_parent_flags = parsed_parent_flags(ref, rr, raw_ref_parent_flags)
    candidate_parent_flags = parsed_parent_flags(candidate, cr, raw_cand_parent_flags)
    missing = set(rr) - set(cr)
    extra = set(cr) - set(rr)
    common = set(rr) & set(cr)
    groups = Counter()
    original_nonzero = Counter()
    candidate_nonzero = Counter()
    differences = Counter()
    for x in rr.values():
        groups[x[2]] += 1
        if abs(x[4]) > abs_tolerance:
            original_nonzero[x[2]] += 1
    for x in cr.values():
        if abs(x[4]) > abs_tolerance:
            candidate_nonzero[x[2]] += 1
    # Original raw VERTEX record order defines the segment traversal of a
    # legacy POLYLINE. Entity-identity and per-vertex coordinate equality alone
    # miss changed topology when a converter reorders unchanged VERTEX records.
    def grouped_vertex_sequence(raw_vertices):
        grouped = defaultdict(list)
        for handle, (parent, _) in raw_vertices.items():
            grouped[parent].append(handle)
        return grouped

    reference_sequences = grouped_vertex_sequence(raw_reference)
    candidate_sequences = grouped_vertex_sequence(raw_candidate)
    for parent in reference_sequences.keys() & candidate_sequences.keys():
        a, b = reference_sequences[parent], candidate_sequences[parent]
        if set(a) == set(b) and a != b:
            differences['vertex_order'] += 1
        if reference_parent_flags[parent] != candidate_parent_flags[parent]:
            differences['parent_polyline_flags'] += 1
    for key in common:
        a, b = rr[key], cr[key]
        if a[:3] != b[:3]:
            differences['owner_or_section'] += 1
        if a[5] != b[5]:
            differences['vertex_role'] += 1
        if any(abs(x - y) > abs_tolerance for x, y in zip(a[3], b[3])):
            differences['xyz'] += 1
        if abs(a[4] - b[4]) > abs_tolerance:
            differences['bulge'] += 1
            if abs(a[4]) > abs_tolerance and abs(b[4]) <= abs_tolerance:
                differences['nonzero_bulge_lost'] += 1
    for (p, identity), sha in zip(captures, digests):
        _unchanged(p, identity, sha)
    clean = not missing and not extra and not any(differences.values())
    return {
        'policy': 'p8p2_ac1032_two_dxf_legacy_vertex_field_parity_read_only_v1',
        'original_dwg_signature': 'AC1032',
        'reference_legacy_vertex_count': len(rr),
        'candidate_legacy_vertex_count': len(cr),
        'reference_legacy_vertex_by_section': dict(sorted(groups.items())),
        'reference_nonzero_bulge_by_section': dict(sorted(original_nonzero.items())),
        'candidate_nonzero_bulge_by_section': dict(sorted(candidate_nonzero.items())),
        'missing_vertex_handles_count': len(missing),
        'extra_vertex_handles_count': len(extra),
        'owner_or_section_difference_count': differences['owner_or_section'],
        'vertex_role_difference_count': differences['vertex_role'],
        'parent_polyline_flags_difference_count': differences['parent_polyline_flags'],
        'parent_vertex_order_difference_count': differences['vertex_order'],
        'xyz_difference_count': differences['xyz'],
        'bulge_difference_count': differences['bulge'],
        'reference_nonzero_bulges_zeroed_in_candidate_count': differences['nonzero_bulge_lost'],
        'original_dwg_vertex_field_truth_verified': False,
        'geometry_approved_for_financial_takeoff': False,
        'financial_quantity_rows_approved': 0,
        'status': ('TWO_DXF_FIELD_PARITY_OBSERVED_SOURCE_UNVERIFIED_NO_GO'
                   if clean else 'LEGACY_VERTEX_CONVERSION_DIFFERENCES_NO_GO'),
    }
