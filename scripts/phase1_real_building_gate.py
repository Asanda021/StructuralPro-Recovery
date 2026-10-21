"""Fail-closed integrity preflight for authentic five-floor acceptance evidence.

A passing preflight means only that files and quantities can be referred for
independent engineering review. It NEVER certifies design or payable BOQ.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import unicodedata

_ID_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _structural_id(value):
    if not isinstance(value, str):
        return ""
    return (unicodedata.normalize("NFKC", value).translate(_ID_DIGITS)
            .replace("ي", "ی").replace("ك", "ک").strip().casefold())


def _positive_decimal(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("explicit quantity string missing")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid quantity") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("invalid non-positive or nonfinite quantity")
    return number


def _check_file(item, root, key, errors):
    if not isinstance(item, dict):
        errors.append(f"{key}: invalid evidence record")
        return
    name, claimed = item.get("path"), item.get("sha256")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{key}: missing file path")
        return
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] == ".git":
        errors.append(f"{key}: unsafe evidence path")
        return
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
        errors.append(f"{key}: actual file bytes unavailable")
        return
    if not isinstance(claimed, str) or len(claimed) != 64:
        errors.append(f"{key}: SHA-256 missing")
        return
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != claimed.lower():
        errors.append(f"{key}: SHA-256 mismatch")


def audit_real_building(manifest: dict, root: Path) -> dict:
    """Never treat a self-declared approval or reviewer name as verification."""
    errors = []
    if not isinstance(manifest, dict):
        return {"candidate_ready_for_external_review": False,
                "engineering_accepted": False, "issues": ["no valid manifest"]}
    if manifest.get("mode") != "real_approved_drawings":
        errors.append("not an actual approved drawing submission")
    if not isinstance(manifest.get("building_id"), str) or not manifest["building_id"].strip():
        errors.append("building ID missing")
    floors = manifest.get("floors")
    if not isinstance(floors, list) or len(floors) != 5:
        errors.append("five explicit floors required")
        floors = []
    floor_ids = [f.get("id") for f in floors if isinstance(f, dict)]
    if (len(floor_ids) != len(floors) or
            any(not isinstance(fid, str) or not fid.strip() for fid in floor_ids) or
            len({_structural_id(fid) for fid in floor_ids}) != len(floor_ids)):
        errors.append("invalid/duplicated floor identities")
    drawings = manifest.get("drawings")
    if not isinstance(drawings, list):
        errors.append("drawings list invalid")
        drawings = []
    disciplines, drawing_ids = set(), set()
    for index, item in enumerate(drawings):
        key = f"drawing[{index}]"
        _check_file(item, root, key, errors)
        if not isinstance(item, dict):
            continue
        if item.get("discipline") in {"structure", "architecture"}:
            disciplines.add(item["discipline"])
        if not isinstance(item.get("revision"), str) or not item["revision"].strip():
            errors.append(f"{key}: revision missing")
        ref = item.get("id")
        if not isinstance(ref, str) or not ref.strip() or ref in drawing_ids:
            errors.append(f"{key}: missing or duplicate drawing ID")
        if isinstance(ref, str):
            drawing_ids.add(ref)
    if not {"structure", "architecture"}.issubset(disciplines):
        errors.append("structural and architectural drawings required")
    oracles = manifest.get("independent_oracles")
    if not isinstance(oracles, list):
        errors.append("independent quantity records missing")
        oracles = []
    covered_floors, physical_ids = set(), set()
    for index, item in enumerate(oracles):
        key = f"oracle[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{key}: invalid record")
            continue
        floor_id, physical_id = item.get("floor_id"), item.get("physical_id")
        source_id = item.get("drawing_id")
        if _structural_id(floor_id) not in {_structural_id(fid) for fid in floor_ids} or not _structural_id(physical_id):
            errors.append(f"{key}: invalid explicit member/floor")
        if not isinstance(source_id, str) or source_id not in drawing_ids:
            errors.append(f"{key}: drawing source missing")
        pair = (_structural_id(floor_id), _structural_id(physical_id))
        if pair in physical_ids:
            errors.append(f"{key}: duplicate physical ownership")
        physical_ids.add(pair)
        covered_floors.add(_structural_id(floor_id))
        # An equal numeric value in mismatched or unknown units is not evidence
        # of an equal measured quantity. Both oracles must declare physical units.
        approved_units = {"m", "m2", "m3", "kg", "عدد"}
        unit = item.get("unit")
        software_unit = item.get("software_unit")
        if not isinstance(unit, str) or unit not in approved_units:
            errors.append(f"{key}: unsupported or missing reference unit")
        if not isinstance(software_unit, str) or software_unit not in approved_units:
            errors.append(f"{key}: unsupported or missing software unit")
        elif software_unit != unit:
            errors.append(f"{key}: unit mismatch between independent and software quantity")
        try:
            if _positive_decimal(item.get("independent_quantity")) != _positive_decimal(item.get("software_quantity")):
                errors.append(f"{key}: quantity differs from independent oracle")
        except ValueError:
            errors.append(f"{key}: invalid quantity")
        revision = item.get("source_revision")
        if not isinstance(revision, str) or not revision.strip():
            errors.append(f"{key}: revision missing")
        elif isinstance(source_id, str):
            drawing = next((d for d in drawings if isinstance(d, dict) and d.get("id") == source_id), None)
            if drawing is not None and revision != drawing.get("revision"):
                errors.append(f"{key}: source revision mismatch")
    if len(covered_floors) != 5:
        errors.append("at least one independent oracle per floor required")
    reviews = manifest.get("external_review_documents")
    if not isinstance(reviews, list) or not reviews:
        errors.append("external professional review document missing")
    else:
        for index, item in enumerate(reviews):
            _check_file(item, root, f"review[{index}]", errors)
    return {"candidate_ready_for_external_review": not errors,
            "engineering_accepted": False, "financially_approved": False,
            "issues": errors, "floor_count": len(floors),
            "independent_quantity_count": len(oracles),
            "review_requirement": "An authorized engineer must independently check actual drawings, quantities and attestations"}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = audit_real_building(manifest, args.source_root)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"candidate_ready_for_external_review": False,
                          "engineering_accepted": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["candidate_ready_for_external_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
