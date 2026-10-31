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
    selectable_types = {"LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "TEXT", "MTEXT", "DIMENSION"}
    for e in document.entities:
        typ = e.entity_type
        data = e.data
        types[typ] += 1
        if data.get("unsupported_measurement"):
            unmeasured[typ] += 1
        if data.get("layer_visible") is False:
            not_visible[typ] += 1
        can_draw = (
            typ == "LINE" and data.get("start") is not None and data.get("end") is not None
            or typ in {"LWPOLYLINE", "POLYLINE", "ARC"} and len(data.get("display_points", data.get("points", ()))) >= 2
            or typ == "CIRCLE" and data.get("center") is not None and data.get("radius") is not None
            or typ in {"TEXT", "MTEXT", "DIMENSION"} and bool(data.get("text"))
        )
        if not can_draw:
            not_drawn[typ] += 1
    return {
        "source_entity_count": sum(types.values()),
        "source_by_type": dict(sorted(types.items())),
        "unmeasurable_by_type": dict(sorted(unmeasured.items())),
        "not_drawn_by_type": dict(sorted(not_drawn.items())),
        "hidden_layer_by_type": dict(sorted(not_visible.items())),
        "not_drawn_count": sum(not_drawn.values()),
        "unmeasurable_count": sum(unmeasured.values()),
        "complete_visual_fidelity": not not_drawn and not not_visible,
        "all_entities_approved_for_takeoff": False,
        "decoder_warning": "Unsupported/proxy/3D/XREF/SHX elements require explicit source evidence and specialist support",
    }
