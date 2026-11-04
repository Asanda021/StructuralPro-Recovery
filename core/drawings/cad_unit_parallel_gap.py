"""Evidence-gated parallel LINE pair reference for unitless DWG.

Geometric match does not prove sheet/member/revision identity; these require
independent evidence and review. The function MUST NOT infer a unit.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import math
from pathlib import Path


def _decimal(value, name):
    try:
        out = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {name}") from exc
    if not out.is_finite():
        raise ValueError(f"Nonfinite {name}")
    return out


def _xy0(point):
    if not isinstance(point, (list, tuple)) or len(point) not in (2, 3):
        raise ValueError("Reference LINE coordinates must be 2D/3D")
    vals = tuple(float(v) for v in point)
    if not all(math.isfinite(v) for v in vals):
        raise ValueError("Nonfinite CAD geometry")
    if len(vals) == 3 and abs(vals[2]) > 1e-10:
        raise ValueError("Nonplanar LINE cannot calibrate a plan gap")
    return vals[:2]


def parallel_line_gap_raw(first, second):
    """Return perpendicular spacing of two genuinely overlapping parallel LINEs."""
    a, b = _xy0(first['start']), _xy0(first['end'])
    c, d = _xy0(second['start']), _xy0(second['end'])
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = d[0] - c[0], d[1] - c[1]
    alen, blen = math.hypot(vx, vy), math.hypot(wx, wy)
    if not all(math.isfinite(z) and z > 1e-9 for z in (alen, blen)):
        raise ValueError("Zero or invalid LINE")
    ux, uy = vx / alen, vy / alen
    angle_error = abs(ux * wy - uy * wx) / blen
    if angle_error > 1e-8:
        raise ValueError("LINE pair is not parallel")
    nx, ny = -uy, ux
    gap = abs((c[0] - a[0]) * nx + (c[1] - a[1]) * ny)
    if not math.isfinite(gap) or gap <= 1e-9:
        raise ValueError("Co-linear or zero-gap LINEs")
    cproj = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
    dproj = (d[0] - a[0]) * ux + (d[1] - a[1]) * uy
    overlap = min(alen, max(cproj, dproj)) - max(0.0, min(cproj, dproj))
    if overlap <= max(1e-8, gap):
        raise ValueError("LINE pair lacks meaningful parallel overlap")
    return gap


def _evidence_rect(rect_values, bounds, label):
    import fitz
    if (not isinstance(rect_values, (tuple, list)) or len(rect_values) != 4):
        raise ValueError(f"Missing or invalid {label} evidence bounding box")
    try:
        rect = fitz.Rect(*[float(v) for v in rect_values])
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid {label} evidence bounding box") from exc
    if (not all(math.isfinite(v) for v in (rect.x0,rect.y0,rect.x1,rect.y1))
            or rect.is_empty or not bounds.contains(rect)
            or rect.get_area() > bounds.get_area() * 0.20):
        raise ValueError(f"Oversized/out-of-bounds {label} evidence region")
    return rect


def validate_parallel_gap_references(document, proof, factor):
    """Validate v3 reference contract; no automatic member or unit inference.

    v3: two independent pairs, source/PDF SHA and matching project revision,
    reviewed member mappings and exact CAD geometry, within <=0.1 mm tolerance.
    """
    if proof.get('policy') != 'cad_unit_reference_v3':
        raise ValueError("Unsupported parallel gap evidence policy")
    source = Path(str(document.source))
    pdf = Path(str(proof.get('source_pdf_path', '')))
    if (source.suffix.lower() != '.dwg' or not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != document.source_sha256
            or not pdf.is_file() or pdf.suffix.lower() != '.pdf'
            or hashlib.sha256(pdf.read_bytes()).hexdigest() != proof.get('source_pdf_sha256')):
        raise ValueError("DWG and same-source PDF hash evidence is required")
    proj = str(proof.get('project_id', '')).strip()
    rev = str(proof.get('drawing_revision', '')).strip()
    if (not proj or not rev or proj.lower() in ('unknown','none','n/a')
            or rev.lower() in ('unknown','none','n/a')
            or proj != str(proof.get('pdf_project_id', '')).strip()
            or rev != str(proof.get('pdf_drawing_revision', '')).strip()):
        raise ValueError("DWG/PDF identity and revision must be documented as equal")
    refs = proof.get('references')
    if not isinstance(refs, list) or not 2 <= len(refs) <= 20:
        raise ValueError("At least two independent reference members required")
    tol = _decimal(proof.get('absolute_tolerance_m'), 'absolute_tolerance_m')
    if not Decimal('0') <= tol <= Decimal('0.0001'):
        raise ValueError("Tolerance outside documented <=0.1 mm window")
    unit_factor = _decimal(factor, 'unit conversion factor')
    if unit_factor <= 0:
        raise ValueError("Positive supported conversion factor required")
    import fitz
    # Bind every declaration to inspectable text in the *actual* PDF, not merely to
    # self-reported JSON strings. Text-free/scanned sheets require independent manual
    # approval and must not silently become unit-calibration evidence.
    identity = proof.get('pdf_identity_evidence')
    if not isinstance(identity, dict):
        raise ValueError("Verified PDF project/revision evidence is missing")
    project_anchor = str(identity.get('project_text', '')).strip()
    revision_anchor = str(identity.get('revision_text', '')).strip()
    identity_page = identity.get('page')
    if (type(identity_page) is not int or not project_anchor or not revision_anchor
            or proj not in project_anchor or rev not in revision_anchor):
        raise ValueError("PDF identity anchors are not bound to project/revision")
    with fitz.open(pdf) as pdf_doc:
        pages = len(pdf_doc)
        if not 1 <= identity_page <= pages:
            raise ValueError("PDF identity page invalid")
        pdf_identity_page = pdf_doc[identity_page - 1]
        identity_rect = _evidence_rect(identity.get('bbox'), pdf_identity_page.rect, 'title-block')
        identity_text = pdf_identity_page.get_textbox(identity_rect)
        if project_anchor not in identity_text or revision_anchor not in identity_text:
            raise ValueError("PDF does not actually contain claimed project/revision in verified title area")
        pdf_page_sizes = [p.rect for p in pdf_doc]
    seen_pdf_locations = set()
    seen_pdf_regions = []

    seen_handles, seen_members, seen_segments = set(), set(), set()
    seen_pair_geometry = []
    def _same_segment(left, right):
        a, b = left
        c, d = right
        return (math.dist(a,c) <= 1e-8 and math.dist(b,d) <= 1e-8) or (math.dist(a,d) <= 1e-8 and math.dist(b,c) <= 1e-8)
    def _same_pair(left, right):
        return ((_same_segment(left[0],right[0]) and _same_segment(left[1],right[1])) or
                (_same_segment(left[0],right[1]) and _same_segment(left[1],right[0])))
    entities_by_handle = {}
    for entity in document.entities:
        if entity.handle:
            entities_by_handle.setdefault(str(entity.handle), []).append(entity)
    for ref in refs:
        if not isinstance(ref, dict) or ref.get('reference_kind') != 'parallel_line_gap':
            raise ValueError("Reference must explicitly describe a parallel LINE gap")
        handles = ref.get('reference_handles')
        member = str(ref.get('member_id', '')).strip()
        sheet = str(ref.get('sheet_id', '')).strip()
        page = ref.get('pdf_page')
        note = str(ref.get('reviewed_pdf_member_mapping', '')).strip()
        if (not isinstance(handles, list) or len(handles) != 2
                or not all(isinstance(h, str) and h.strip() for h in handles)
                or handles[0] == handles[1] or any(h in seen_handles for h in handles)
                or not member or member in seen_members or not sheet or not note
                or type(page) is not int or not 1 <= page <= pages):
            raise ValueError("Unique pair, member, sheet, page and independent mapping note required")
        # Independent printed reference must be present on the exact claimed page.
        # Document-unit claims are not source proof without a visible numeric label.
        printed_member = str(ref.get('pdf_member_label', '')).strip()
        printed_dimension = str(ref.get('pdf_dimension_text', '')).strip()
        printed_unit = str(ref.get('pdf_unit', '')).strip().lower()
        unit_scale = {'m': Decimal('1'), 'cm': Decimal('0.01'),
                      'mm': Decimal('0.001'), 'متر': Decimal('1'),
                      'سانت': Decimal('0.01'), 'سانتی متر': Decimal('0.01'),
                      'سانتی‌متر': Decimal('0.01'), 'میلی متر': Decimal('0.001'),
                      'میلی‌متر': Decimal('0.001')}.get(printed_unit)
        printed_number = _decimal(ref.get('pdf_dimension_value'), 'pdf_dimension_value')
        rect = _evidence_rect(ref.get('pdf_evidence_bbox'), pdf_page_sizes[page - 1], 'member')
        if any(prev_page == page and rect.intersects(prev_rect)
               for prev_page, prev_rect in seen_pdf_regions):
            raise ValueError("Printed member evidence regions must not overlap")
        with fitz.open(pdf) as proof_pdf:
            anchored_text = proof_pdf[page - 1].get_textbox(rect)
        if (not printed_member or not printed_dimension or unit_scale is None
                or printed_number <= 0 or printed_member not in anchored_text
                or printed_dimension not in anchored_text):
            raise ValueError("PDF member and dimension must be visible together inside exact source region")
        if abs(printed_number * unit_scale - _decimal(ref.get('real_length_m'), 'real_length_m')) > tol:
            raise ValueError("Printed PDF dimension disagrees with declared real-world length")
        if printed_unit not in printed_dimension:
            raise ValueError("Printed dimension lacks explicit matching unit")
        pdf_location = (page, printed_member, printed_dimension)
        if pdf_location in seen_pdf_locations:
            raise ValueError("Two references cannot reuse the same printed PDF member/dimension")
        seen_pdf_locations.add(pdf_location)
        seen_pdf_regions.append((page,rect))
        lines = []
        for handle in handles:
            match = entities_by_handle.get(handle, [])
            if len(match) != 1 or match[0].entity_type != 'LINE':
                raise ValueError("Each reference handle must resolve to one LINE")
            entity = match[0]
            if (entity.data.get('unsupported_measurement')
                    or entity.data.get('layer_visible') is not True
                    or entity.data.get('layer_defined') is not True):
                raise ValueError("Unverified or hidden LINE is not accepted")
            lines.append(entity.data)
        raw_gap = parallel_line_gap_raw(lines[0], lines[1])
        pair_geometry = tuple((_xy0(d['start']), _xy0(d['end'])) for d in lines)
        if any(_same_pair(pair_geometry, earlier) for earlier in seen_pair_geometry):
            raise ValueError("Distinct handles with duplicate source geometry are not independent references")
        proposed = _decimal(ref.get('cad_length'), 'cad_length')
        real = _decimal(ref.get('real_length_m'), 'real_length_m')
        if proposed <= 0 or real <= 0:
            raise ValueError("Positive dimensions required")
        if not math.isclose(raw_gap, float(proposed), rel_tol=1e-12, abs_tol=1e-8):
            raise ValueError("Claimed spacing differs from handle geometry")
        if abs(proposed * unit_factor - real) > tol:
            raise ValueError("Real-world dimension conflicts with stated conversion")
        segment_key = tuple(sorted(handles))
        if segment_key in seen_segments:
            raise ValueError("Duplicate physical reference")
        seen_segments.add(segment_key)
        seen_pair_geometry.append(pair_geometry)
        seen_handles.update(handles)
        seen_members.add(member)
    return True