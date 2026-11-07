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
    """Audit *observed* MAP/AEC dictionary links, without source completeness claims.

    A missing namespace is never healthy evidence.  Proxy/custom targets are
    indeterminate even if a handle exists in the DXF entity database.  Do not
    reconstruct or modify an original or converted drawing.
    """
    candidates = []
    for obj in dxf_document.objects:
        if obj.dxftype() == 'DICTIONARY' and any(
                name in obj for name in ('Autodesk_MAP', 'AEC_VARS')):
            candidates.append(obj)
    if len(candidates) > 1:
        return {
            'policy': 'p8p2_dxf_named_dictionary_links_v1',
            'root_dictionary_handle': None, 'namespaces': {},
            'dangling_or_invalid_count': None,
            'dangling_or_invalid_references': [],
            'unverified_target_count': None,
            'unverified_target_references': [],
            'converted_dxf_namespace_integrity_status': 'AMBIGUOUS_NAMED_DICTIONARY_ROOTS',
            'original_dwg_custom_payloads_verified': False,
            'source_coverage_verified': False, 'financial_quantity_approved': False,
            'automatic_patch_authorized': False,
        }
    root = candidates[0] if candidates else dxf_document.rootdict
    findings = []
    namespaces = {}
    empty_named_dictionaries = []
    namespace_owner_unverified = 0
    class_names = {str(c.dxf.name).upper() for c in dxf_document.classes}
    # Structural link resolution for a small set of *standard* DXF objects
    # does not imply that an embedded proprietary payload was understood.
    standard_links = frozenset({
        'DICTIONARY', 'ACDBDICTIONARYWDFLT', 'DICTIONARYVAR', 'XRECORD',
    })
    proxy_types = frozenset({'ACAD_PROXY_OBJECT', 'ACAD_PROXY_ENTITY'})
    indeterminate = False

    def resolve(value):
        if isinstance(value, str):
            handle = value.strip().upper()
            if not handle or any(c not in '0123456789ABCDEF' for c in handle):
                return None, handle
            return dxf_document.entitydb.get(handle), handle
        try:
            handle = str(value.dxf.handle).upper()
        except (TypeError, AttributeError, ValueError):
            return None, ''
        # A supplied object is not enough: its handle must exist in this DXF.
        return dxf_document.entitydb.get(handle), handle

    for namespace in ('Autodesk_MAP', 'AEC_VARS'):
        raw_child = root.get(namespace)
        if raw_child is None:
            namespaces[namespace] = 'NOT_PRESENT_IN_DXF'
            continue
        child, child_handle = resolve(raw_child)
        if child is None:
            namespaces[namespace] = 'UNRESOLVED_NAMESPACE_ROOT'
            findings.append({'namespace': namespace, 'key': '<root>',
                             'target_handle': child_handle,
                             'reason': 'ROOT_TARGET_UNRESOLVED'})
            continue
        if child.dxftype() != 'DICTIONARY':
            namespaces[namespace] = 'WRONG_NAMESPACE_OBJECT_TYPE'
            findings.append({'namespace': namespace, 'key': '<root>',
                             'target_handle': child_handle,
                             'reason': 'ROOT_NOT_DICTIONARY'})
            continue
        # A handle which resolves to a DICTIONARY is not enough to establish
        # that it is truly the named child of this root. Check the DXF-level
        # owner; an orphan/aliased namespace may masquerade as a preserved
        # MAP/AEC dictionary while source semantics remain completely absent.
        dxf_fields = getattr(child, 'dxf', None)
        getter = getattr(dxf_fields, 'get', None)
        # Real ezdxf namespace attributes expose .get; lightweight tests
        # may expose .owner directly. Missing values remain unverified.
        try:
            owner_value = getter('owner', None) if callable(getter) else getattr(dxf_fields, 'owner', None)
        except (TypeError, AttributeError, ValueError):
            owner_value = None
        owner = str(owner_value).strip().upper() if owner_value is not None else ''
        expected_owner = str(root.dxf.handle).strip().upper()
        if owner != expected_owner:
            namespace_owner_unverified += 1
            namespaces[namespace] = 'NAMESPACE_OWNER_UNVERIFIED'
            indeterminate = True
            findings.append({'namespace': namespace, 'key': '<root>',
                             'target_handle': child_handle,
                             'reason': 'NAMESPACE_OWNER_MISMATCH'})
        else:
            namespaces[namespace] = 'DICTIONARY_PRESENT'
        if len(child) == 0:
            # An empty imported namespace says nothing about the original DWG's
            # custom instances. Do not promote missing links to clean source data.
            empty_named_dictionaries.append(namespace)
        for key, value in child.items():
            target, handle = resolve(value)
            if target is None:
                findings.append({'namespace': namespace, 'key': str(key),
                                 'target_handle': handle, 'reason': 'DANGLING_DXF_HANDLE'})
                continue
            kind = str(target.dxftype()).upper()
            if kind in proxy_types:
                indeterminate = True
                findings.append({'namespace': namespace, 'key': str(key),
                                 'target_handle': handle,
                                 'reason': 'PROXY_TARGET_UNVERIFIED'})
            elif kind not in standard_links:
                indeterminate = True
                findings.append({'namespace': namespace, 'key': str(key),
                                 'target_handle': handle,
                                 'reason': ('CUSTOM_TARGET_UNVERIFIED'
                                            if kind in class_names
                                            else 'TARGET_CLASS_NOT_DECLARED')})
    if any(f['reason'] in {'DANGLING_DXF_HANDLE', 'ROOT_TARGET_UNRESOLVED',
                            'ROOT_NOT_DICTIONARY'} for f in findings):
        status = 'BROKEN_DXF_DICTIONARY_LINKS'
    elif indeterminate:
        status = 'INDETERMINATE_DXF_DICTIONARY_TARGETS'
    elif all(v == 'NOT_PRESENT_IN_DXF' for v in namespaces.values()):
        status = 'NAMESPACES_ABSENT_NO_EVIDENCE'
    elif any(v == 'NOT_PRESENT_IN_DXF' for v in namespaces.values()):
        status = 'NAMESPACES_INCOMPLETE_NO_EVIDENCE'
    elif empty_named_dictionaries:
        status = 'EMPTY_NAMED_NAMESPACE_SOURCE_UNVERIFIED'
    else:
        status = 'NO_DANGLING_LINKS_OBSERVED_IN_TARGETED_NAMESPACES'
    unresolved_reasons = frozenset({
        'DANGLING_DXF_HANDLE', 'ROOT_TARGET_UNRESOLVED', 'ROOT_NOT_DICTIONARY',
    })
    broken = [finding for finding in findings if finding['reason'] in unresolved_reasons]
    unverified = [finding for finding in findings if finding['reason'] not in unresolved_reasons]
    # A reference to an existing proxy is UNVERIFIED, not DANGLING.  Keep the
    # disjoint sets and counts independently auditable.
    return {
        'policy': 'p8p2_dxf_named_dictionary_links_v1',
        'root_dictionary_handle': str(root.dxf.handle),
        'namespaces': namespaces,
        'dangling_or_invalid_count': len(broken),
        'dangling_or_invalid_references': broken,
        'unverified_target_count': len(unverified),
        'unverified_target_references': unverified,
        'empty_namespace_count': len(empty_named_dictionaries),
        'empty_namespaces': tuple(empty_named_dictionaries),
        'namespace_owner_unverified_count': namespace_owner_unverified,
        'unverified_namespace_count': sum(
            v == 'NOT_PRESENT_IN_DXF' for v in namespaces.values()),
        'converted_dxf_namespace_integrity_status': status,
        'original_dwg_custom_payloads_verified': False,
        'source_coverage_verified': False,
        'financial_quantity_approved': False,
        'automatic_patch_authorized': False,
    }
