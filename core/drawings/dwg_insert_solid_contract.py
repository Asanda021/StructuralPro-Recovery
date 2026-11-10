"""Read-only DWG-vs-DXF selected BLOCK/SOLID consistency gate.

Never converts a consistency result into payable geometry approval. This code
checks selected native attributes, NOT full DWG object/payload equivalence.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from importlib import metadata
import math
from pathlib import Path
from typing import Any

MAX_DWG_BYTES = 50 * 1024 * 1024
MAX_DXF_BYTES = 300 * 1024 * 1024
MAX_SOURCE_ENTITIES = 1_000_000
_UNSPECIFIED_EXTRUSION = object()


def _same(x: Any, y: Any) -> bool:
    a, b = float(x), float(y)
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, abs_tol=1e-7, rel_tol=0.0)


def _vec_equal(a: Any, b: Any, count: int = 3) -> bool:
    try:
        left, right = tuple(a), tuple(b)
        return len(left) == len(right) == count and all(_same(x, y) for x, y in zip(left, right))
    except (TypeError, ValueError, OverflowError):
        return False


def verify_insert_fields(source: Any, target: Any, source_layer: str) -> list[str]:
    """Check selected INSERT transform/visibility/source layer; no name comparison."""
    errors = []
    a, b = source.dxf, target.dxf
    if target.dxftype() != "INSERT":
        return ["INSERT_TYPE_CHANGED"]
    if source_layer != str(b.layer):
        errors.append("INSERT_LAYER_CHANGED")
    if not _vec_equal(a.get("insert"), b.insert):
        errors.append("INSERT_POSITION_CHANGED")
    if not _vec_equal(a.get("extrusion", (0, 0, 1)), b.get("extrusion", (0, 0, 1))):
        errors.append("INSERT_EXTRUSION_CHANGED")
    for fld, default in (("xscale", 1), ("yscale", 1), ("zscale", 1), ("rotation", 0)):
        if not _same(a.get(fld, default), b.get(fld, default)):
            errors.append("INSERT_" + fld.upper() + "_CHANGED")
    if bool(a.get("invisible", False)) != bool(b.get("invisible", False)):
        errors.append("INSERT_VISIBILITY_CHANGED")
    return errors


def verify_block_line(source: Any, target: Any, source_layer: str) -> list[str]:
    """Compare a LINE definition member, bound to the original handle."""
    if target.dxftype() != "LINE" or str(source.dxftype) != "LINE":
        return ["BLOCK_MEMBER_TYPE_CHANGED"]
    errors = []
    if source_layer != str(target.dxf.layer):
        errors.append("BLOCK_LINE_LAYER_CHANGED")
    if not _vec_equal(source.dxf.get("start"), target.dxf.start):
        errors.append("BLOCK_LINE_START_CHANGED")
    if not _vec_equal(source.dxf.get("end"), target.dxf.end):
        errors.append("BLOCK_LINE_END_CHANGED")
    if bool(source.dxf.get("invisible", False)) != bool(target.dxf.get("invisible", False)):
        errors.append("BLOCK_LINE_VISIBILITY_CHANGED")
    return errors


def classify_solid_height(source_vertices: Any, target_vertices: Any, elevation: Any, extrusion: Any,
                          *, target_extrusion: Any = _UNSPECIFIED_EXTRUSION) -> str:
    """Distinguish exact 3D preservation vs legacy elevation relocation.

    Legacy elevation alone is NOT proof a 3D viewer reconstructs correct WCS.
    Any non-default extrusion needs independent transformation/oracle.
    """
    try:
        a, b = [tuple(v) for v in source_vertices], [tuple(v) for v in target_vertices]
    except (TypeError, ValueError, OverflowError):
        return "SOLID_UNREADABLE"
    if len(a) != 4 or len(b) != 4 or any(len(x) != 3 for x in a + b):
        return "SOLID_TOPOLOGY_UNVERIFIED"
    if target_extrusion is not _UNSPECIFIED_EXTRUSION and not _vec_equal(extrusion, target_extrusion):
        return "SOLID_EXTRUSION_CHANGED"
    if not _vec_equal(extrusion, (0, 0, 1)):
        return "SOLID_NONSTANDARD_EXTRUSION_UNVERIFIED"
    if any(not _same(x[0], y[0]) or not _same(x[1], y[1]) for x, y in zip(a, b)):
        return "SOLID_XY_CHANGED"
    if all(_same(x[2], y[2]) for x, y in zip(a, b)):
        return "SOLID_3D_VERTEX_MATCH"
    try:
        z = float(elevation)
    except (ValueError, TypeError, OverflowError):
        return "SOLID_Z_MISMATCH_NO_LEGACY_ELEVATION"
    if (math.isfinite(z) and all(_same(x[2], z) for x in a)
            and all(_same(y[2], 0) for y in b)):
        return "SOLID_Z_IN_LEGACY_ELEVATION_VIEWER_UNVERIFIED"
    return "SOLID_Z_MISMATCH"


def _digest(path: Path, maximum: int) -> str:
    if (not path.is_file() or path.is_symlink()
            or not 100 < path.stat().st_size <= maximum):
        raise ValueError("Source unavailable, symlinked or outside bounded size")
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_insert_solid(original_dwg: str | Path, diagnostic_dxf: str | Path,
                       expected_dwg_sha: str, expected_dxf_sha: str) -> dict:
    """Native original DWG vs separately decoded DXF; always PARTIAL_NO_GO.

    Provenance is limited to named BLOCK_RECORD mapping and supported LINE
    geometries. The anonymous block object graph and other types are not certified.
    """
    src, dst = Path(original_dwg), Path(diagnostic_dxf)
    if src.suffix.lower() != ".dwg" or dst.suffix.lower() != ".dxf":
        raise ValueError("DWG and diagnostic DXF paths required")
    for expected in (expected_dwg_sha, expected_dxf_sha):
        if not isinstance(expected, str) or len(expected) != 64 or any(x not in "0123456789abcdef" for x in expected.lower()):
            raise ValueError("A pinned SHA256 is mandatory for each file")
    sha_src = _digest(src, MAX_DWG_BYTES)
    sha_dst = _digest(dst, MAX_DXF_BYTES)
    if sha_src != expected_dwg_sha.lower() or sha_dst != expected_dxf_sha.lower():
        raise ValueError("Original DWG/DXF SHA256 mismatch")
    if metadata.version("ezdwg") != "0.17.0":
        raise ValueError("Pinned ezdwg==0.17.0 required")
    import ezdwg
    import ezdxf
    source = ezdwg.read(str(src))
    if source.version != src.open("rb").read(6).decode("ascii"):
        raise ValueError("Native DWG header not consistent with reader")
    target = ezdxf.readfile(str(dst))
    layers = {int(l.handle): str(l.name) for l in source.layers}
    header_rows = list(ezdwg.raw.decode_block_header_names(str(src)))
    block_names = defaultdict(set)
    for handle, name, *_ in header_rows:
        block_names[int(handle)].add(str(name))
    source_inserts = {}
    renames = {}
    for entity in source.modelspace().iter_entities(types="INSERT", include_styles=True):
        if len(source_inserts) >= MAX_SOURCE_ENTITIES:
            raise ValueError("Too many native INSERTs")
        handle = int(entity.handle)
        if handle in source_inserts:
            raise ValueError("Native duplicate INSERT handle")
        source_inserts[handle] = entity
        converted = target.entitydb.get(format(handle, "X"))
        if converted is None or converted.dxftype() != "INSERT":
            raise ValueError("INSERT missing or retyped in converted DXF")
        layer_handle = entity.dxf.get("layer_handle")
        if layer_handle is None or int(layer_handle) not in layers:
            raise ValueError("Native INSERT layer unverified")
        issues = verify_insert_fields(entity, converted, layers[int(layer_handle)])
        if issues:
            raise ValueError("INSERT source transform changed: " + ",".join(issues))
        old, new = str(entity.dxf.get("name", "")), str(converted.dxf.name)
        if old != new:
            if new not in target.blocks:
                raise ValueError("Renamed INSERT target BLOCK missing")
            record_hex = str(target.blocks[new].block_record_handle)
            record = int(record_hex, 16)
            if block_names.get(record) != {old}:
                raise ValueError("Native BLOCK_RECORD identity does not support rename")
            renames[handle] = (old, new, record)

    definitions = {}
    if renames:
        requested = {r for _, _, r in renames.values()}
        source_members = defaultdict(dict)
        count = 0
        for entity in source.entities().iter_entities(include_styles=True):
            count += 1
            if count > MAX_SOURCE_ENTITIES:
                raise ValueError("Native entity roster limit exceeded")
            placement = source.entity_placement(entity.handle)
            if not placement or placement[1] not in requested:
                continue
            owner = placement[1]
            if entity.handle in source_members[owner]:
                raise ValueError("Duplicate native member handle")
            source_members[owner][entity.handle] = entity
        for _, (_, name, record) in sorted(renames.items()):
            if record in definitions:
                continue
            block = target.blocks[name]
            if int(str(block.block_record_handle), 16) != record:
                raise ValueError("DXF BLOCK_RECORD changed")
            native_members = source_members[record]
            dxf_members = {}
            for e in block:
                h = int(e.dxf.handle, 16)
                if h in dxf_members:
                    raise ValueError("Duplicate destination BLOCK member")
                dxf_members[h] = e
            if not native_members or set(native_members) != set(dxf_members):
                raise ValueError("BLOCK member handle roster not preserved")
            issues = []
            for handle, ent in native_members.items():
                if str(ent.dxftype) != "LINE":
                    raise ValueError("Only LINE-only BLOCK definitions are compared")
                native_layer_handle = ent.dxf.get("layer_handle")
                if native_layer_handle is None or int(native_layer_handle) not in layers:
                    raise ValueError("Native BLOCK member layer unknown")
                issues.extend(verify_block_line(ent, dxf_members[handle], layers[int(native_layer_handle)]))
            if issues:
                raise ValueError("BLOCK member geometry/layer changed: " + ",".join(issues[:5]))
            definitions[record] = len(native_members)

    solid_results = defaultdict(int)
    solid_examples = defaultdict(list)
    source_solid_handles = set()
    for entity in source.modelspace().iter_entities(types="SOLID", include_styles=True):
        h = int(entity.handle)
        if h in source_solid_handles:
            raise ValueError("Duplicate source SOLID handle")
        source_solid_handles.add(h)
        converted = target.entitydb.get(format(h, "X"))
        if converted is None or converted.dxftype() != "SOLID":
            raise ValueError("SOLID missing or changed type")
        raw_vertices = [tuple(getattr(converted.dxf, "vtx" + str(i))) for i in range(4)]
        mode = classify_solid_height(entity.dxf.get("points"), raw_vertices,
                                     converted.dxf.get("elevation", None),
                                     entity.dxf.get("extrusion", (0, 0, 1)),
                                     target_extrusion=converted.dxf.get("extrusion", (0, 0, 1)))
        solid_results[mode] += 1
        if len(solid_examples[mode]) < 12:
            solid_examples[mode].append(format(h, "X"))
    if _digest(src, MAX_DWG_BYTES) != sha_src or _digest(dst, MAX_DXF_BYTES) != sha_dst:
        raise ValueError("DWG/DXF bytes changed during audit")
    return {
        "policy": "p8p2_readonly_block_solid_consistency_v1",
        "reader": "ezdwg==0.17.0 original AC DWG vs ezdxf diagnostic DXF",
        "source_sha256": sha_src,
        "dxf_sha256": sha_dst,
        "source_inserts_checked": len(source_inserts),
        "renamed_insert_count": len(renames),
        "renamed_insert_records": [
            {"insert_handle": format(h, "X"), "source_name": old,
             "converted_name": new, "block_record_handle": format(r, "X")}
            for h, (old, new, r) in sorted(renames.items())
        ],
        "line_only_block_definitions_checked": len(definitions),
        "block_definition_line_members_checked": sum(definitions.values()),
        "block_line_member_count_by_record": {format(k,"X"):v for k,v in sorted(definitions.items())},
        "native_solid_count_checked": len(source_solid_handles),
        "solid_selected_3d_status_counts": dict(sorted(solid_results.items())),
        "solid_selected_status_examples": dict(sorted(solid_examples.items())),
        "renderer_reconstructs_legacy_elevation_verified": False,
        "opaque_map_aec_payloads_verified": False,
        "source_revision_verified": False,
        "financial_quantity_rows_approved": 0,
        "geometry_approved_for_financial_takeoff": False,
        "status": "PARTIAL_NO_GO",
        "limitation": "Checks specific INSERT transformations, LINE-only block members and SOLID encoded Z, not full object graph or rendering."
    }