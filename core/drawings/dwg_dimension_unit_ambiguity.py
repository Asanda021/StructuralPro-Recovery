"""Converted-DXF dimension text diagnostic, NEVER a DWG source-unit oracle.

A numeric DIMENSION override is a label, not a source length, and may be
manual, rounded, style-scaled, false, or unrelated to the depicted member.
Only aggregate counts leave this module, not original source identifiers.
"""
from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any

MAX_DIMENSION_RECORDS = 100_000
_NUMERIC = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\Z", re.ASCII)
_UNIT_TOKEN = re.compile(r"(?<![A-Za-z])(?:mm|cm|m)(?![A-Za-z])", re.IGNORECASE)
_RATIO_BANDS = (1, 10, 100, 1000)


def audit_dxf_dimension_annotation_ratios(document: Any, *, ratio_tolerance: float = 0.01) -> dict:
    """Compare converted DXF numeric labels with ezdxf computed measurements.

    A band only means *numerically close*, never a verified source-unit scale.
    This function does not read the original DWG or decode proprietary glyphs.
    """
    if not isinstance(ratio_tolerance, (int, float)) or isinstance(ratio_tolerance, bool) or not math.isfinite(ratio_tolerance) or not 0 < ratio_tolerance <= 0.02:
        raise ValueError('Invalid strictly limited dimension ratio tolerance')
    if not hasattr(document, 'entitydb') or not hasattr(document, 'modelspace'):
        raise ValueError('Real converted DXF document required')
    model_owner = str(document.modelspace().block_record_handle).upper()
    try:
        unit_code = document.header.get('$INSUNITS')
    except (AttributeError, KeyError, ValueError, TypeError) as exc:
        raise ValueError('Missing or malformed DXF unit header') from exc
    if type(unit_code) is not int or unit_code < 0 or unit_code > 24:
        raise ValueError('Untrusted DXF unit code')
    counts: Counter[str] = Counter()
    seen_handles = set()
    for entity in document.entitydb.values():
        if entity is None or entity.dxftype() != 'DIMENSION':
            continue
        counts['dimension_total'] += 1
        if counts['dimension_total'] > MAX_DIMENSION_RECORDS:
            raise ValueError('Excessive converted DXF dimension records')
        raw_handle = entity.dxf.get('handle', '')
        if not isinstance(raw_handle, str) or not raw_handle or raw_handle in seen_handles:
            raise ValueError('Malformed or duplicate converted DXF dimension identity')
        seen_handles.add(raw_handle)
        if str(entity.dxf.get('owner', '')).upper() == model_owner:
            counts['direct_modelspace_dimension'] += 1
        else:
            counts['outside_direct_modelspace_dimension'] += 1
        label = str(entity.dxf.get('text', '') or '').strip()
        if label in ('', '<>'):
            counts['automatic_or_placeholder_text'] += 1
            continue
        if not _NUMERIC.fullmatch(label):
            counts['nonnumeric_override_text'] += 1
            if _UNIT_TOKEN.search(label):
                counts['nonnumeric_text_with_unit_token'] += 1
            continue
        counts['numeric_override_text'] += 1
        try:
            observed = float(entity.get_measurement())
            displayed = float(label)
        except (TypeError, ValueError, OverflowError, ArithmeticError):
            counts['invalid_numeric_measurement'] += 1
            continue
        if not all(math.isfinite(x) for x in (observed, displayed)) or observed <= 1e-9 or displayed <= 0:
            counts['invalid_numeric_measurement'] += 1
            continue
        ratio = displayed / observed
        if not math.isfinite(ratio):
            counts['invalid_numeric_measurement'] += 1
            continue
        matched = False
        for band in _RATIO_BANDS:
            if math.isclose(ratio, band, rel_tol=ratio_tolerance, abs_tol=0):
                counts[f'annotation_ratio_near_{band}'] += 1
                matched = True
                break
        if not matched:
            counts['annotation_ratio_outside_selected_bands'] += 1
    total = counts['dimension_total']
    if not total:
        raise ValueError('No measurable dimension inventory in diagnostic DXF')
    result = {
        'policy': 'p8p2_converted_dxf_dimension_annotation_ratio_diagnostic_v1',
        'dxf_insunits_code': unit_code,
        'dxf_unit_status': 'UNITLESS_OR_NOT_DECLARED' if unit_code == 0 else 'HEADER_ONLY_NOT_SOURCE_VERIFIED',
        'relative_ratio_tolerance': float(ratio_tolerance),
    }
    tracked = (
        'dimension_total','direct_modelspace_dimension','outside_direct_modelspace_dimension',
        'automatic_or_placeholder_text','nonnumeric_override_text',
        'nonnumeric_text_with_unit_token','numeric_override_text',
        'invalid_numeric_measurement',
        *(f'annotation_ratio_near_{x}' for x in _RATIO_BANDS),
        'annotation_ratio_outside_selected_bands',
    )
    result.update({key: counts[key] for key in tracked})
    result.update({
        'multiple_annotated_ratio_bands_observed': sum(counts[f'annotation_ratio_near_{x}'] > 0 for x in _RATIO_BANDS) > 1,
        'source_dwg_dimstyle_and_units_independently_verified': False,
        'dxf_dimension_label_is_authoritative_measurement': False,
        'source_and_converted_geometry_semantics_verified': False,
        'original_shx_glyph_mapping_verified': False,
        'inferred_original_dwg_unit': None,
        'suggested_automatic_scale_factor': None,
        'geometry_approved_for_financial_takeoff': False,
        'financial_quantities_approved': 0,
        'engineering_verdict': 'DIMENSION_TEXT_UNIT_AMBIGUOUS_NO_GO',
    })
    return result
