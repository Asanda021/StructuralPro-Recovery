"""Diagnostic AC1018 LINE ownership and standard BLOCK reachability."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from hashlib import file_digest
from importlib.metadata import version
import json
from pathlib import Path

from core.drawings.dwg_custom_graph_coverage import _source_handle
from core.drawings.dwg_original_block_source_oracle import _index

_MAX_RECORDS = 250_000
_MAX_MEMBERSHIPS = 500_000
_MAX_DEPTH = 64
_UNVERIFIED = "OWNER_OR_REACHABILITY_UNVERIFIED"
_CONFLICT = "CONFLICTING_OWNERSHIP"


def _member_scope(record, memberships, scopes, explicit_owner=None, *, verify_explicit=False):
    if len(memberships) > 1:
        return _CONFLICT, None
    mode = record.get("entmode")
    owner = _source_handle(record["ownerhandle"]) if "ownerhandle" in record else 0
    if not memberships or type(mode) is not int or mode not in (0, 1, 2):
        return _UNVERIFIED, None
    container = next(iter(memberships))
    scope = scopes.get(container)
    if (owner and owner != container
            or explicit_owner and (explicit_owner != container or mode != 0)
            or mode == 1 and scope != "paper"
            or mode == 2 and scope != "model"):
        return _CONFLICT, None
    if mode == 0 and (not owner or verify_explicit and not explicit_owner):
        return _UNVERIFIED, None
    if mode in (1, 2) and owner:
        return _CONFLICT, None
    return {
        "model": "DIRECT_MODELSPACE_VERIFIED",
        "paper": "DIRECT_PAPERSPACE_VERIFIED",
        None: "BLOCK_DEFINITION_VERIFIED",
    }[scope], container


def summarize_line_ownership(rows, scopes, line_owners, native_references, *,
                             selected_lines=()):
    """Classify unique LINE definitions, then report reachability separately."""
    if (not isinstance(rows, list) or not 0 < len(rows) <= _MAX_RECORDS
            or len(line_owners) > _MAX_RECORDS or len(native_references) > _MAX_RECORDS
            or len(selected_lines) > 64):
        raise ValueError("Unbounded ownership evidence")
    records = {}
    for record in rows:
        handle = _source_handle(record.get("handle"))
        if not handle or handle in records:
            raise ValueError("Duplicate or null DWG object handle")
        records[handle] = record

    blocks = {h for h, r in records.items() if r.get("object") == "BLOCK_HEADER"}
    if (list(scopes.values()).count("model") != 1
            or set(scopes.values()) - {"model", "paper"} or not scopes.keys() <= blocks):
        raise ValueError("Invalid layout root evidence")

    memberships = defaultdict(set)
    member_count = dangling = 0
    for block in blocks:
        members = records[block].get("entities", [])
        member_count += len(members)
        if member_count > _MAX_MEMBERSHIPS:
            raise ValueError("Unbounded BLOCK membership evidence")
        for member in members:
            handle = _source_handle(member)
            if handle not in records:
                dangling += 1
            elif block in memberships[handle]:
                raise ValueError("Duplicate entity in BLOCK membership")
            else:
                memberships[handle].add(block)

    definitions = blocks - scopes.keys()
    edges = defaultdict(set)
    unverified_refs = verified_refs = 0
    for handle, record in records.items():
        kind = record.get("entity", "")
        if kind not in ("INSERT", "MINSERT") and not kind.startswith("DIMENSION_"):
            continue
        key = "block" if kind.startswith("DIMENSION_") else "block_header"
        target = _source_handle(record[key]) if key in record else None
        _, container = _member_scope(record, memberships.get(handle, ()), scopes)
        if container is None or target not in definitions or native_references.get(handle) != target:
            unverified_refs += 1
        else:
            edges[container].add(target)
            verified_refs += 1

    visited = set(scopes)
    queue = deque((root, 0) for root in scopes)
    depth_limited = False
    nested_block_count = 0
    while queue:
        node, depth = queue.popleft()
        for target in edges[node]:
            if target in visited:
                continue
            if depth == _MAX_DEPTH:
                depth_limited = True
                continue
            visited.add(target)
            nested_block_count += depth > 0
            queue.append((target, depth + 1))

    statuses = Counter()
    reachable_lines = 0
    selected = {}
    requested = set(selected_lines)
    for handle, record in records.items():
        if record.get("entity") != "LINE":
            continue
        status, container = _member_scope(
            record, memberships.get(handle, ()), scopes, line_owners.get(handle),
            verify_explicit=True,
        )
        if handle not in line_owners and status != _CONFLICT:
            status, container = _UNVERIFIED, None
        statuses[status] += 1
        reachable = status == "BLOCK_DEFINITION_VERIFIED" and container in visited
        reachable_lines += reachable
        if handle in requested:
            selected[handle] = {
                "membership": status, "container": container,
                "reachability": "REFERENCED_BLOCK_REACHABLE_VERIFIED" if reachable else _UNVERIFIED,
            }
    if len(selected) != len(selected_lines):
        raise ValueError("Selected LINE evidence missing or repeated")
    return {
        "status": "PARTIAL_NO_GO",
        "line_membership": dict(statuses),
        "standard_reachable_line_count": reachable_lines,
        "standard_reachable_block_count": len(visited) - len(scopes),
        "standard_nested_only_block_count": nested_block_count,
        "verified_standard_reference_count": verified_refs,
        "unverified_standard_reference_count": unverified_refs,
        "layout_root_count": len(scopes),
        "dangling_block_memberships": dangling,
        "reachability_depth_limited": depth_limited,
        "selected_lines": selected,
        "opaque_map_aec_reachability_verified": False,
        "source_units_verified": False,
        "geometry_approved_for_financial_takeoff": False,
        "financial_quantity_rows_approved": 0,
    }


def _checked_file(path, expected, limit):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Missing or unbounded private source")
    before = path.stat()
    with path.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError("Private source SHA mismatch")
    after = path.stat()
    def identity(st):
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

    if identity(before) != identity(after):
        raise ValueError("Private source changed during hash")
    return identity(after)


def audit_original_line_ownership(dwg_path, native_json, *, dwg_sha256,
                                  native_json_sha256, selected_lines=()):
    """Compare frozen LibreDWG JSON evidence with pinned reads of the original."""
    dwg, decoded = Path(dwg_path), Path(native_json)
    sources = ((dwg, dwg_sha256, 50 << 20), (decoded, native_json_sha256, 128 << 20))
    snapshots = [_checked_file(*source) for source in sources]
    if version("ezdwg") != "0.17.0":
        raise ValueError("Pinned original DWG reader required")
    import ezdwg

    path = str(dwg)
    if ezdwg.raw.detect_version(path) != "AC1018":
        raise ValueError("AC1018 original source required")
    rows = json.loads(decoded.read_bytes())["OBJECTS"]
    if not isinstance(rows, list) or not 0 < len(rows) <= _MAX_RECORDS:
        raise ValueError("Unbounded LibreDWG object roster")
    raw_layouts = {_source_handle(row["handle"]): row for row in rows if row.get("object") == "LAYOUT"}
    scopes = {}
    for layout in ezdwg.read(path).layouts().values():
        handle = layout["block_record_handle"]
        matching = raw_layouts.get(layout["handle"])
        if (matching is None or _source_handle(matching.get("block_header")) != handle
                or handle in scopes):
            raise ValueError("Independent layout root evidence disagrees")
        scopes[handle] = "model" if layout["model"] else "paper"
    if len(scopes) != len(raw_layouts):
        raise ValueError("Independent layout root roster incomplete")

    lines = _index(ezdwg.raw.decode_line_owner_handles(path), "LINE owners")
    inserts = _index(ezdwg.raw.decode_insert_write_properties(path), "INSERT references", min_cols=3)
    dimensions = _index(
        [row for _, row in ezdwg.raw.decode_dimension_entities(path)],
        "DIMENSION references", min_cols=11,
    )
    if inserts.keys() & dimensions.keys():
        raise ValueError("Independent standard reference identities overlap")
    refs = {h: row[2] for h, row in inserts.items()}
    refs.update({h: row[10][1] for h, row in dimensions.items()})
    receipt = summarize_line_ownership(
        rows, scopes, {h: row[1] for h, row in lines.items()}, refs,
        selected_lines=selected_lines,
    )
    if [_checked_file(*source) for source in sources] != snapshots:
        raise ValueError("Private source changed during audit")
    return {
        **receipt, "source_dwg_sha256": dwg_sha256, "libredwg_json_sha256": native_json_sha256,
        "source_format": "AC1018", "independent_reader": "ezdwg==0.17.0",
    }
