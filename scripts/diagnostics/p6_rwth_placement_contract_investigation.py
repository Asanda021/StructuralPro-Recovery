"""Sanitized diagnosis of pinned, published RWTH ventilation IFC4 placement.

Investigation only: no source transformation, geometry export, BOQ or product
changes. All temporary IFC bytes remain on the ephemeral GitHub runner.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.diagnostics.p6_independent_ifc_public_reference import (
    authenticated_download, REV,
)

KNOWN_ERRORS = {
    "نوع Placement پشتیبانی نمی‌شود": "UNSUPPORTED_OBJECT_PLACEMENT_TYPE",
    "Placement باید سه‌بعدی صریح باشد": "RELATIVE_AXIS_PLACEMENT_NOT_3D",
    "جهت محورهای Placement متعامد نیست": "NON_ORTHOGONAL_AXIS_DIRECTIONS",
    "چرخه یا عمق نامعتبر Placement": "PLACEMENT_CYCLE_OR_DEPTH",
    "جهت محور صفر است": "ZERO_DIRECTION_VECTOR",
    "جهت محور سه‌بعدی معتبر نیست": "DIRECTION_NOT_3D",
    "مختصات خارج از دامنه معتبر است": "LOCAL_ORIGIN_OUT_OF_RANGE",
    "مختصات جهانی خارج از دامنه معتبر است": "GLOBAL_ORIGIN_OUT_OF_RANGE",
    "واحد IFC خارج از قرارداد SI معتبر است": "UNSUPPORTED_SI_UNIT",
    "واحد طول IFC نامشخص است": "MISSING_LENGTH_UNIT",
    "نوع واحد IFC تکراری است": "DUPLICATE_SI_UNIT",
}
TOLERANCES = (
    ("gt_1e24", Decimal("1e-24")),
    ("gt_1e12", Decimal("1e-12")),
    ("gt_1e8", Decimal("1e-8")),
    ("gt_1e6", Decimal("1e-6")),
)


def safe_type(entity):
    return entity.is_a() if entity is not None else "NONE"


def run_analysis(path: Path) -> dict:
    import ifcopenshell
    from core.drawings.bim_adapter import BIMAdapter

    model = ifcopenshell.open(str(path))
    row = {
        "kind": "phase6_g2_source_placement_investigation_v1",
        "source_repo": "RWTH-E3D/DigitalHub",
        "source_commit": REV,
        "is_published_reference_not_client_building": True,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema": str(model.schema),
        "elements": len(model.by_type("IfcElement")),
        "storeys": len(model.by_type("IfcBuildingStorey")),
        "map_conversion_count": len(model.by_type("IfcMapConversion")),
        "quantity_authority": False,
        "acceptance_gate_status": "OPEN_DIAGNOSTIC_ONLY",
    }
    local = model.by_type("IfcLocalPlacement")
    kinds = Counter()
    context_types = Counter()
    axial_defects = Counter()
    normalized_dot_bands = Counter()
    axis_pair_count = 0
    max_parent_depth = 0
    cycles = 0
    for pl in local:
        r = getattr(pl, "RelativePlacement", None)
        kinds[safe_type(r)] += 1
        if r is None or not r.is_a("IfcAxis2Placement3D"):
            continue
        try:
            with localcontext() as ctx:
                ctx.prec = 80
                zdir = getattr(r, "Axis", None)
                xdir = getattr(r, "RefDirection", None)
                z = [Decimal(str(v)) for v in zdir.DirectionRatios] if zdir else [
                    Decimal(0), Decimal(0), Decimal(1)]
                x = [Decimal(str(v)) for v in xdir.DirectionRatios] if xdir else [
                    Decimal(1), Decimal(0), Decimal(0)]
                if len(x) != 3 or len(z) != 3:
                    axial_defects["DIRECTION_DIMENSION"] += 1
                    continue
                znorm = sum(v * v for v in z).sqrt()
                xnorm = sum(v * v for v in x).sqrt()
                if not znorm or not xnorm:
                    axial_defects["ZERO_VECTOR"] += 1
                    continue
                dot = abs(sum(a * b for a, b in zip(x, z)) / (xnorm * znorm))
                axis_pair_count += 1
                for key, threshold in TOLERANCES:
                    if dot > threshold:
                        normalized_dot_bands[key] += 1
        except (InvalidOperation, ValueError, TypeError, AttributeError, OverflowError):
            axial_defects["AXIS_DECIMAL_UNREADABLE"] += 1

    for typ, objects in [
        ("IfcElement", model.by_type("IfcElement")),
        ("IfcBuildingStorey", model.by_type("IfcBuildingStorey")),
    ]:
        obj_counts = Counter(safe_type(getattr(o, "ObjectPlacement", None)) for o in objects)
        context_types[typ + ":missing"] = obj_counts["NONE"]
        context_types[typ + ":nonlocal"] = sum(
            count for kind, count in obj_counts.items()
            if kind not in ("NONE", "IfcLocalPlacement")
        )
    # This source-only graph check is independent of BIMAdapter's transform.
    for pl in local:
        visited = set()
        current = pl
        depth = 0
        while current is not None and current.is_a("IfcLocalPlacement"):
            if current.id() in visited:
                cycles += 1
                break
            visited.add(current.id())
            depth += 1
            if depth > len(local) + 1:
                cycles += 1
                break
            current = current.PlacementRelTo
        max_parent_depth = max(max_parent_depth, depth)
    row["placement_counts"] = {
        "local_placements": len(local),
        "relative_placement_types": dict(sorted(kinds.items())),
        "object_placement_context": dict(sorted(context_types.items())),
        "max_parent_chain_depth": max_parent_depth,
        "parent_chain_cycle_count": cycles,
        "axis_pairs_checked": axis_pair_count,
        "axis_issues": dict(sorted(axial_defects.items())),
        "absolute_normalized_dot_exceeds": dict(sorted(normalized_dot_bands.items())),
    }
    # Run original product validator unchanged. Never emit raw exception text:
    # it can contain original object identifiers or absolute paths.
    try:
        BIMAdapter().read_document(path, revision="RWTH-PLACEMENT-DIAGNOSTIC")
    except Exception as exc:
        row["original_contract"] = "REJECTED"
        row["exception_class"] = type(exc).__name__
        row["normalized_error"] = KNOWN_ERRORS.get(str(exc), "UNCLASSIFIED_SOURCE_CONTRACT")
        row["error_message_published"] = False
    else:
        row["original_contract"] = "ACCEPTED"
        row["normalized_error"] = "NONE"
    return row


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="p6-rwth-placement-") as t:
        temp = Path(t)
        path = temp / "ventilation.ifc"
        provenance = authenticated_download("ventilation", path)
        row = run_analysis(path)
        if row["source_sha256"] != provenance["source_sha256"]:
            raise RuntimeError("INDEPENDENT_SOURCE_SHA_MISMATCH")
        row["source_blob_and_size_verified"] = provenance["source_git_blob_sha1_verified"]
    out = Path("p6-placement-diagnostic")
    out.mkdir(exist_ok=False)
    (out / "summary.json").write_text(
        json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # Only the sanitized aggregate summary is printed or archived.
    print(json.dumps({
        "original_contract": row["original_contract"],
        "normalized_error": row["normalized_error"],
        "placements": row["placement_counts"]["local_placements"],
        "relative_types": row["placement_counts"]["relative_placement_types"],
    }, ensure_ascii=False))
    if row["schema"] != "IFC4" or not row["source_blob_and_size_verified"]:
        raise SystemExit("VERIFICATION_GUARD_FAILED")


if __name__ == "__main__":
    main()
