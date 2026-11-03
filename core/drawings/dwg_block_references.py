"""Bounded, read-only evidence of references to BLOCK definitions in raw ASCII DXF.

Checks INSERT and DIMENSION group-code 2 references, including nested blocks.
An absence of readable references is NOT proof of non-use in the original DWG.
This diagnostic never alters the CAD file or approves measurement/financial use.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

_MAX_BYTES = 250 * 1024 * 1024
_MAX_RECORDS = 1_000_000
_MAX_PAIRS = 12_000_000


def audit_raw_dxf_block_references(
    path: str | Path, target_block_record_handle: str,
) -> dict:
    """Trace observed DXF references by target BLOCK_RECORD handle.

    The target is the raw BLOCK header's group 330, not the BLOCK entity's
    group 5. INSERT and DIMENSION reference block *names* via group 2.
    References under BLOCKS are reachable only when a top-level reference
    traverses their parent block. All statuses remain diagnostic-only.
    """
    target = str(target_block_record_handle).strip().upper()
    try:
        int(target, 16)
    except (TypeError, ValueError) as exc:
        raise ValueError("Target block-record handle must be hexadecimal") from exc
    if not target or len(target) > 32:
        raise ValueError("Invalid target block-record handle")
    source = Path(path)
    if not source.is_file() or not 0 < source.stat().st_size <= _MAX_BYTES:
        raise ValueError("Raw DXF absent or exceeds audit size limit")

    definitions: list[tuple[str, str]] = []
    refs: list[tuple[str | None, str, str]] = []
    section = ""
    block = ""
    current_type: str | None = None
    fields: dict[str, str] = {}
    records = 0
    uncertain_text = False

    def finish() -> None:
        nonlocal section, block, records, uncertain_text
        if current_type is None:
            return
        records += 1
        if records > _MAX_RECORDS:
            raise ValueError("Raw DXF reference record limit exceeded")
        if current_type == "SECTION":
            section = fields.get("2", "").upper()
        elif current_type == "ENDSEC":
            section = ""
            block = ""
        elif current_type == "BLOCK" and section == "BLOCKS":
            block = fields.get("2", "")
            definitions.append((block.casefold(), fields.get("330", "").upper()))
            uncertain_text |= not bool(block) or "\ufffd" in block
        elif current_type == "ENDBLK" and section == "BLOCKS":
            block = ""
        elif current_type in {"INSERT", "DIMENSION"} and section in {"ENTITIES", "BLOCKS"}:
            name = fields.get("2", "")
            if not name or "\ufffd" in name or (section == "BLOCKS" and not block):
                uncertain_text = True
            refs.append((block.casefold() if section == "BLOCKS" else None,
                         name.casefold(), current_type))

    with source.open("rb") as stream:
        if stream.read(22).startswith(b"AutoCAD Binary DXF"):
            raise ValueError("Binary DXF is not supported by this diagnostic")
        stream.seek(0)
        for pair_index in range(_MAX_PAIRS + 1):
            code = stream.readline()
            if not code:
                break
            if pair_index == _MAX_PAIRS:
                raise ValueError("Raw DXF reference pair limit exceeded")
            value = stream.readline()
            if not value:
                raise ValueError("Truncated raw DXF pair")
            key = code.strip().decode("ascii", errors="strict")
            if not key.isdecimal():
                raise ValueError("Invalid raw DXF group code")
            text = value.rstrip(b"\r\n").decode("utf-8", errors="replace").strip()
            if key == "0":
                finish()
                current_type = text.upper()
                fields = {}
            elif current_type is not None and key in {"2", "330"}:
                fields[key] = text
        else:
            raise ValueError("Raw DXF reference pair limit exceeded")
        finish()

    target_names = {name for name, handle in definitions if handle == target and name}
    name_counts: dict[str, int] = defaultdict(int)
    for name, _ in definitions:
        if name:
            name_counts[name] += 1
    ambiguous_names = {name for name, count in name_counts.items() if count > 1}
    defined_names = set(name_counts)
    raw_insert_count = sum(kind == "INSERT" for _, _, kind in refs)
    raw_dimension_count = sum(kind == "DIMENSION" for _, _, kind in refs)

    graph: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for parent, referenced, kind in refs:
        if parent is not None:
            graph[parent].append((referenced, kind))
    roots = [(name, kind) for parent, name, kind in refs if parent is None]
    direct_target = sum(name in target_names for name, _ in roots)
    all_target = sum(name in target_names for _, name, _ in refs)

    # A referenced parent may itself contain INSERTs or DIMENSION block
    # references. Traverse names with a visited set to bound cyclic blocks.
    reachable = set()
    stack = [name for name, _ in roots]
    while stack:
        name = stack.pop()
        if name in reachable:
            continue
        reachable.add(name)
        if len(reachable) > _MAX_RECORDS:
            raise ValueError("Block reference chain limit exceeded")
        stack.extend(child for child, _ in graph.get(name, ()))

    visible_target = bool(target_names & reachable)
    unknown_references = sum(
        bool(name) and name not in defined_names for _, name, _ in refs
    )
    ambiguous_reference = bool(ambiguous_names & reachable)
    uncertain = uncertain_text or ambiguous_reference or not target_names
    if not target_names:
        status = "RAW_TARGET_BLOCK_RECORD_NOT_FOUND"
    elif uncertain:
        status = "RAW_BLOCK_REFERENCE_CHAIN_UNRESOLVED"
    elif visible_target:
        status = "RAW_DXF_OBSERVED_REFERENCED_BLOCK"
    else:
        status = "RAW_DXF_NO_OBSERVED_BLOCK_REFERENCE_NOT_PROOF_UNUSED"
    return {
        "status": status,
        "target_block_definition_count": len(target_names),
        "observed_raw_insert_count": raw_insert_count,
        "observed_raw_dimension_count": raw_dimension_count,
        "observed_direct_target_references": direct_target,
        "observed_any_target_references": all_target,
        "observed_reachable_target": visible_target,
        "observed_unknown_named_references": unknown_references,
        "ambiguous_reachable_names": ambiguous_reference,
        "complete_original_dwg_reference_coverage_verified": False,
        "financial_quantity_approved": False,
    }
