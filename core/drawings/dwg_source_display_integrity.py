"""Fail-closed read-only DXF SOLID WCS and named-dictionary diagnostics.

This module never authorizes source completeness, 3D GUI rendering, engineering
units or payable quantity. It does not modify DXF input or synthesize proxies.
"""
from __future__ import annotations

import math
from typing import Any

_MAX_ABS_COORD = 1e12


def _point3(value: Any) -> tuple[float, float, float]:
    try:
        coordinates = tuple(float(n) for n in value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Invalid SOLID vertex coordinates') from exc
    if (len(coordinates) != 3 or not all(math.isfinite(n) and abs(n) <= _MAX_ABS_COORD
                                          for n in coordinates)):
        raise ValueError('SOLID vertex is not finite bounded XYZ')
    return coordinates


def _near(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=1e-7, rel_tol=1e-12)


def source_solid_3d_preview_manifest(points: Any, extrusion: Any = (0, 0, 1)) -> dict:
    """Retain actual native original-DWG vertices for diagnostics, not an IFC mesh.

    The native CAD viewer itself currently draws a 2D footprint. A raw 3D
    vertex receipt is NOT evidence that the product's 3D UI rendered it.
    """
    vertices = tuple(_point3(v) for v in points)
    if len(vertices) not in (3, 4):
        raise ValueError('Native SOLID requires three or four vertices')
    ext = _point3(extrusion)
    if not all(_near(x, y) for x, y in zip(ext, (0, 0, 1))):
        raise ValueError('Nonstandard SOLID extrusion needs independent WCS proof')
    return {
        'native_source_vertices_3d': [list(v) for v in vertices],
        'source_vertices_3d_preserved': True,
        'cad_3d_gui_render_verified': False,
        'source_preview_geometry_status': 'NATIVE_XYZ_RECEIPT_2D_VIEW_ONLY',
        'financial_quantity_approved': False,
    }


def converted_dxf_solid_3d_diagnostic(entity: Any) -> dict:
    """Bounded diagnostic of SOLID XYZ when DXF moved Z to legacy group-38.

    Only default extrusion and a consistent *single* elevation permit display
    coordinate reconstruction. It is not automatically used by a 3D product UI.
    """
    if entity.dxftype() != 'SOLID':
        raise ValueError('Expected DXF SOLID')
    data = entity.dxf
    vertices = tuple(_point3(data.get('vtx' + str(i))) for i in range(4))
    ext = _point3(data.get('extrusion', (0, 0, 1)))
    if not all(_near(x, y) for x, y in zip(ext, (0, 0, 1))):
        return _unverified('NONSTANDARD_EXTRUSION_3D_UNVERIFIED')
    try:
        elevation = float(data.get('elevation', 0))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Invalid DXF group 38 elevation') from exc
    if not math.isfinite(elevation) or abs(elevation) > _MAX_ABS_COORD:
        raise ValueError('Nonfinite or excessive DXF SOLID elevation')
    if _near(elevation, 0):
        final = vertices
        status = 'WCS_VERTEX_Z_PRESENT_DIAGNOSTIC_ONLY'
    elif all(_near(v[2], 0) for v in vertices):
        final = tuple((v[0], v[1], elevation) for v in vertices)
        status = 'GROUP38_ELEVATION_RECONSTRUCTED_DIAGNOSTIC_ONLY'
    else:
        return _unverified('MIXED_VERTEX_Z_AND_ELEVATION_AMBIGUOUS')
    if any(not all(math.isfinite(c) and abs(c) <= _MAX_ABS_COORD for c in v) for v in final):
        raise ValueError('Reconstructed SOLID coordinates outside safe range')
    return {
        'status': status, 'diagnostic_wcs_vertices_3d': [list(v) for v in final],
        'cad_3d_gui_render_verified': False,
        'source_geometry_independently_verified': False,
        'financial_quantity_approved': False,
    }


def _unverified(reason: str) -> dict:
    return {'status': reason, 'diagnostic_wcs_vertices_3d': None,
            'cad_3d_gui_render_verified': False,
            'source_geometry_independently_verified': False,
            'financial_quantity_approved': False}


def audit_named_dictionary_links(dxf_document: Any) -> dict:
    """Check two targeted converted-DXF dictionary namespaces, not DWG payload.

    A missing link is a failure in the *output DXF*. An absent namespace is
    'NOT_PRESENT', never evidence that all original DWG objects were kept.
    """
    # Converted files may contain a newly synthesized ezdxf root dictionary
    # *and* the actual imported named-object dictionary in OBJECTS. Scanning
    # only doc.rootdict would hide the three known broken MAP/AEC references.
    candidates = []
    for obj in dxf_document.objects:
        if obj.dxftype() != 'DICTIONARY':
            continue
        if any(key in obj for key in ('Autodesk_MAP', 'AEC_VARS')):
            candidates.append(obj)
    if len(candidates) > 1:
        return {
            'policy': 'p8p2_dxf_named_dictionary_links_v1',
            'root_dictionary_handle': None,
            'namespaces': {},
            'dangling_or_invalid_count': None,
            'dangling_or_invalid_references': [],
            'converted_dxf_namespace_integrity_status': 'AMBIGUOUS_NAMED_DICTIONARY_ROOTS',
            'original_dwg_custom_payloads_verified': False,
            'source_coverage_verified': False,
            'financial_quantity_approved': False,
        }
    root = candidates[0] if candidates else dxf_document.rootdict
    findings = []
    namespaces = {}
    for namespace in ('Autodesk_MAP', 'AEC_VARS'):
        child = root.get(namespace)
        if child is None:
            namespaces[namespace] = 'NOT_PRESENT_IN_DXF'
            continue
        if isinstance(child, str):
            namespaces[namespace] = 'UNRESOLVED_NAMESPACE_ROOT'
            findings.append({'namespace': namespace, 'key': '<root>',
                             'target_handle': child.upper(), 'reason': 'ROOT_TARGET_UNRESOLVED'})
            continue
        if child.dxftype() != 'DICTIONARY':
            namespaces[namespace] = 'WRONG_NAMESPACE_OBJECT_TYPE'
            findings.append({'namespace': namespace, 'key': '<root>',
                             'target_handle': str(child.dxf.handle), 'reason': 'ROOT_NOT_DICTIONARY'})
            continue
        namespaces[namespace] = 'DICTIONARY_PRESENT'
        for key, entity in child.items():
            try:
                handle = entity.upper() if isinstance(entity, str) else str(entity.dxf.handle).upper()
                resolved = dxf_document.entitydb.get(handle)
            except (TypeError, ValueError, AttributeError) as exc:
                raise ValueError('Unreadable DXF dictionary link') from exc
            if resolved is None:
                findings.append({'namespace': namespace, 'key': str(key),
                                 'target_handle': handle, 'reason': 'DANGLING_DXF_HANDLE'})
    return {
        'policy': 'p8p2_dxf_named_dictionary_links_v1',
        'root_dictionary_handle': str(root.dxf.handle),
        'namespaces': namespaces, 'dangling_or_invalid_count': len(findings),
        'dangling_or_invalid_references': findings,
        'converted_dxf_namespace_integrity_status': (
            'BROKEN_DXF_DICTIONARY_LINKS' if findings else 'NO_DANGLING_LINKS_OBSERVED_IN_TARGETED_NAMESPACES'),
        'original_dwg_custom_payloads_verified': False,
        'source_coverage_verified': False,
        'financial_quantity_approved': False,
    }