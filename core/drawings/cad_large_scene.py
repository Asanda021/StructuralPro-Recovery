"""Constant-extra-memory CAD viewport bounds for large source drawings.

All source entities remain in the model and in the audit. This computes only
preview extents; neither bounds nor renderer sampling authorize measurements.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Iterable


def cad_preview_index(entities: Iterable) -> tuple[tuple[float, float, float, float], dict[str, int], dict[str, int]]:
    """Stream finite CAD coordinates without retaining a second vertex array.

    Return xmin,xmax,ymin,ymax, layer counts, and counts by exact source type.
    This function deliberately does not skip unknown types in the accounting.
    """
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")
    layers, types = Counter(), Counter()

    def point(x, y):
        nonlocal xmin, xmax, ymin, ymax
        x, y = float(x), float(y)
        if not isfinite(x) or not isfinite(y):
            raise ValueError("CAD preview includes non-finite coordinates")
        xmin, xmax = min(xmin, x), max(xmax, x)
        ymin, ymax = min(ymin, y), max(ymax, y)

    for entity in entities:
        layers[entity.layer] += 1
        types[entity.entity_type] += 1
        data = entity.data
        for path in data.get("display_paths", ()):
            for xy in path:
                point(xy[0], xy[1])
        for xy in data.get("display_points", data.get("points", ())):
            point(xy[0], xy[1])
        for key in ("start", "end", "center", "insert"):
            xy = data.get(key)
            if xy is not None:
                point(xy[0], xy[1])
        if entity.entity_type == "CIRCLE" and data.get("center") is not None:
            x, y = data["center"]
            r = float(data.get("radius", 0))
            if not isfinite(r) or r < 0:
                raise ValueError("Invalid CAD circle radius")
            point(x-r, y-r)
            point(x+r, y+r)
    return (
        (xmin, xmax, ymin, ymax) if isfinite(xmin) else (0.0, 1.0, 0.0, 1.0),
        dict(layers), dict(types),
    )


def cad_entity_drawable(entity):
    """Match the canvas drawing branches; capability is separate from approval."""
    typ, data = entity.entity_type, entity.data
    if data.get("preview_decode_error"):
        return False
    return bool(
        typ == "LINE" and data.get("start") is not None and data.get("end") is not None
        or typ in {"LWPOLYLINE", "POLYLINE", "ARC", "SPLINE", "ELLIPSE", "SOLID"}
        and len(data.get("display_points", data.get("points", ()))) >= 2
        or typ == "HATCH" and bool(data.get("display_paths"))
        or typ == "CIRCLE" and data.get("center") is not None and float(data.get("radius", 0)) > 0
        or typ in {"TEXT", "MTEXT", "DIMENSION"} and bool(data.get("text"))
    )


def cad_coverage_details(document):
    """Stream an auditable roster without making another large entity array."""
    for entity in document.entities:
        data = entity.data
        drawn = cad_entity_drawable(entity)
        yield {"type": entity.entity_type, "layer": entity.layer,
               "handle": entity.handle, "block_path": data.get("handle_path", entity.handle),
               "display_state": ("FAILED" if data.get("preview_decode_error") else
                                 "HIDDEN" if drawn and data.get("layer_visible") is False else
                                 "DRAWABLE" if drawn else "UNSUPPORTED_DISPLAY"),
               "measurable": not bool(data.get("unsupported_measurement") or data.get("preview_only")),
               "reason": data.get("preview_decode_error") or data.get("unsupported_measurement") or "",
               "display_fidelity": data.get("display_fidelity", "SOURCE_PRIMITIVE"),
               "font_status": data.get("text_status", "")}


def cad_coverage_report(document):
    """Count all recognized, unrendered, and unmeasurable source entities.

    Display fidelity and engineering quantity acceptance are independent.
    A source may open successfully while requiring another decoder for proxy
    objects, XREFs, SHX, solid bodies, dimensions, or HATCH boundaries.
    """
    types = Counter()
    unmeasured = Counter()
    not_drawn = Counter()
    not_visible = Counter()
    partition = Counter({"DRAWABLE": 0, "HIDDEN": 0, "UNSUPPORTED_DISPLAY": 0, "FAILED": 0})
    failed = Counter()
    fidelity_unverified = False
    for e in document.entities:
        typ = e.entity_type
        data = e.data
        types[typ] += 1
        if data.get("unsupported_measurement"):
            unmeasured[typ] += 1
        if data.get("layer_visible") is False:
            not_visible[typ] += 1
        can_draw = cad_entity_drawable(e)
        if data.get("preview_decode_error"):
            failed[typ] += 1
            partition["FAILED"] += 1
        elif can_draw:
            partition["HIDDEN" if data.get("layer_visible") is False else "DRAWABLE"] += 1
        else:
            partition["UNSUPPORTED_DISPLAY"] += 1
        if data.get("font_notice") or str(data.get("display_fidelity", "")).startswith("BOUNDARIES_ONLY"):
            fidelity_unverified = True
        if not can_draw:
            not_drawn[typ] += 1
    return {
        "source_entity_count": sum(types.values()),
        "decoded_entity_count": sum(types.values()),
        "source_count_basis": document.conversion.get("source_count_basis", "EXPANDED_DECODED_ENTITIES"),
        "original_source_count_verified": document.conversion.get("original_source_count_verified", False),
        "display_partition": dict(partition),
        "display_partition_reconciled": sum(partition.values()) == len(document.entities),
        "failed_geometry_count": sum(failed.values()),
        "failed_geometry_by_type": dict(sorted(failed.items())),
        "source_by_type": dict(sorted(types.items())),
        "unmeasurable_by_type": dict(sorted(unmeasured.items())),
        "not_drawn_by_type": dict(sorted(not_drawn.items())),
        "hidden_layer_by_type": dict(sorted(not_visible.items())),
        "not_drawn_count": sum(not_drawn.values()),
        "unmeasurable_count": sum(unmeasured.values()),
        "complete_visual_fidelity": not not_drawn and not not_visible and not fidelity_unverified,
        "all_entities_approved_for_takeoff": False,
        "decoder_warning": "Unsupported/proxy/3D/XREF/SHX elements require explicit source evidence and specialist support",
    }
