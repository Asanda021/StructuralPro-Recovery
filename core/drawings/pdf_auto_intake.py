"""Non-interactive multi-sheet PDF semantic intake (P8/P2-A, T01/T02/T05/T11).

Safely extracts *explicit* member-type marks and nearby dimension statements.
No scanned-line/object classification, quantity of physical occurrences, material
pricing or payable BOQ can be derived from this output.  Any unproven tie is a
review question carrying traceable evidence instead of a guessed takeoff row.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import math
import re
from typing import Iterable, Mapping

from core.drawings.pdf_grid_instances import detect_vector_grid_positions
from core.drawings.pdf_vector_symbol_witness import compact_symbol_witness
from core.drawings.pdf_vector_type_labels import vector_column_type_labels
from core.drawings.pdf_sheet_scope_registration import (
    classify_sheet_title, register_column_grid_against_axes,
)
from core.drawings.pdf_column_position_ledger import compile_column_position_ledger
from core.drawings.pdf_sheet_detail_inventory import (
    inventory_pdf_page_regions, assemble_pdf_detail_inventory,
)
from core.drawings.pdf_detail_object_index import build_pdf_detail_object_index
from core.drawings.pdf_multidiscipline_gap_register import build_pdf_multidiscipline_gap_register
from core.drawings.pdf_operator_component_review import build_pdf_operator_component_review
from core.drawings.pdf_detail_evidence_graph import (
    build_pdf_detail_evidence_graph, read_pdf_page_declarations,
)
from core.drawings.pdf_engine import require_current_pdf
from core.drawings.pdf_beam_axis_crosscheck import extract_pdf_axis_grid_witness
from core.drawings.pdf_beam_end_support_review import extract_pdf_beam_end_markers
from core.drawings.pdf_rendered_text_recovery import (
    recover_page_rendered_type_words, should_recover_rendered_labels,
)


_MEMBER_MARK = re.compile(
    r"(?<![A-Za-z0-9])(?P<family>BR|BP|SC|SW|C|B|W|F|P|S)\s*[-–.]?\s*(?P<index>[1-9][0-9]{0,2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_EXPLICIT_DIM = re.compile(
    r"(?<![A-Za-z0-9])(?P<kind>L|H|W|T)\s*[=:]\s*"
    r"(?P<value>[0-9]+(?:[.٫][0-9]+)?)\s*(?P<unit>mm|cm|m)\b",
    re.IGNORECASE,
)
_UNIT_TO_M = {"mm": Decimal("0.001"), "cm": Decimal("0.01"), "m": Decimal("1")}
_DIM_KIND = {"L": "length", "H": "height", "W": "width", "T": "thickness"}


def _span_center(span: dict) -> tuple[float, float]:
    x0, y0, x1, y1 = span["bbox"]
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _same_rotation(a: tuple[float, float], b: tuple[float, float]) -> bool:
    al = math.hypot(*a)
    bl = math.hypot(*b)
    return al > 0 and bl > 0 and (a[0] * b[0] + a[1] * b[1]) / (al * bl) >= 0.985


def _score_pair(member: dict, dimension: dict) -> float | None:
    """Geometric proximity in the SAME orientation, never text-order matching."""
    if not _same_rotation(member["direction"], dimension["direction"]):
        return None
    ax, ay = _span_center(member)
    bx, by = _span_center(dimension)
    dx, dy = bx - ax, by - ay
    ux, uy = member["direction"]
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    along = abs(dx * ux + dy * uy)
    across = abs(-dx * uy + dy * ux)
    if across > 38 or along > 72:
        return None
    # Prefer closeness across a line. Two equally plausible witnesses are blocked.
    return round(across * 1.3 + along, 6)


def _parse_pdf_lines(page) -> tuple[list[dict], list[dict]]:
    marks: list[dict] = []
    dimensions: list[dict] = []
    for block in page.get_text("dict").get("blocks", ()):
        for line in block.get("lines", ()):
            direction = tuple(line.get("dir") or (1.0, 0.0))
            for span in line.get("spans", ()):
                raw = str(span.get("text") or "")
                if not raw.strip():
                    continue
                geom = {"bbox": tuple(round(float(x), 3) for x in span["bbox"]),
                        "direction": tuple(round(float(x), 6) for x in direction),
                        "printed": raw}
                for match in _MEMBER_MARK.finditer(raw):
                    # No assumed construction trade, floor, count or physical instance.
                    marks.append({**geom, "tag": match.group("family").upper() + str(int(match.group("index")))})
                for match in _EXPLICIT_DIM.finditer(raw):
                    value_text = match.group("value").replace("٫", ".")
                    try:
                        value = Decimal(value_text) * _UNIT_TO_M[match.group("unit").lower()]
                    except (InvalidOperation, KeyError):
                        continue
                    if value.is_finite() and value > 0:
                        dimensions.append({**geom, "quantity_kind": _DIM_KIND[match.group("kind").upper()],
                                           "quantity_m": str(value), "unit": "m"})
    return marks, dimensions


def inspect_pdf_sheet_set(
    paths: Iterable[str | Path], *, max_documents: int = 100, max_pages: int = 500,
    revision_registry: Mapping | None = None,
    rendered_ocr: bool = False, ocr_language: str = "eng+fas",
    max_ocr_pages: int = 25, member_review: dict | None = None,
    beam_profile_witnesses: list[dict] | None = None,
    beam_axis_labels: dict | None = None,
    beam_detail_profile_witnesses: list[dict] | None = None,
) -> dict:
    """Read every supplied sheet without interactive prompting or any DB/BOQ write.

    Each returned member is a *type/dimension candidate*, never a counted
    physical column/beam/wall or a financially accepted quantity.  Code consuming
    this result must keep review questions and operator UI isolated from BOQ.
    """
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF multi-sheet intake") from exc
    if type(rendered_ocr) is not bool or type(max_ocr_pages) is not int or not 1 <= max_ocr_pages <= 50:
        raise ValueError("PDF optional rendered OCR requires bounded explicit opt-in")
    if rendered_ocr and ocr_language not in {"eng", "fas", "eng+fas", "fas+eng"}:
        raise ValueError("Invalid PDF rendered OCR language")
    received = [Path(item) for item in paths]
    if (type(max_documents) is not int or type(max_pages) is not int or
            not received or len(received) > max_documents or max_pages < 1):
        raise ValueError("PDF intake requires a bounded, nonempty set of sheets")
    if len({str(p.resolve()) for p in received}) != len(received):
        raise ValueError("Duplicate PDF source selection is not allowed")
    documents: list[dict] = []
    raw_members: list[dict] = []
    grid_locations: list[dict] = []
    vector_type_label_evidence: list[dict] = []
    vector_grid_summaries: list[dict] = []
    page_view_summaries: list[dict] = []
    page_detail_summaries: list[dict] = []
    rendered_ocr_pages: list[dict] = []
    beam_axis_grid_candidates: list[dict] = []
    beam_end_marker_pages: list[dict] = []
    ocr_attempts = 0
    page_reasons: list[dict] = []
    source_digests: set[str] = set()
    total_pages = 0
    for path in received:
        if path.suffix.lower() != ".pdf" or not path.is_file():
            raise ValueError("Every selected drawing must be an existing PDF")
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        if digest in source_digests:
            raise ValueError("Duplicate PDF source identity")
        source_digests.add(digest)
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.is_repaired or not doc.is_pdf or not len(doc):
                raise ValueError("PDF source is unreadable, repaired or encrypted")
            total_pages += len(doc)
            if total_pages > max_pages:
                raise ValueError("PDF page-count limit exceeded")
            doc_id = f"PDF{len(documents) + 1:03d}"
            pdf_metadata = doc.metadata or {}
            documents.append({"document_id": doc_id, "page_count": len(doc),
                              "source_name": path.name, "sha256": digest,
                              "metadata": {key: str(pdf_metadata[key])[:250]
                                           for key in ("title", "creationDate", "modDate") if pdf_metadata.get(key)}})
            for number, page in enumerate(doc, 1):
                try:
                    title_scope = classify_sheet_title(page.get_text())
                except (RuntimeError, ValueError, MemoryError):
                    title_scope = classify_sheet_title("")
                page_view_summaries.append({
                    'document_id': doc_id, 'page': number, **title_scope,
                })
                axis_witness = None
                if title_scope.get('status') == 'EXPLICIT_SHEET_TITLE' and title_scope.get('sheet_kind') == 'axis_plan':
                    axis_witness = extract_pdf_axis_grid_witness(
                        page, document_id=doc_id, page_number=number,
                        source_sha256=digest, source_name=path.name,
                    )
                    beam_axis_grid_candidates.append(axis_witness)
                if title_scope.get('status') == 'EXPLICIT_SHEET_TITLE' and title_scope.get('sheet_kind') == 'beam_layout_plan':
                    grids = [grid for grid in beam_axis_grid_candidates
                             if (grid['document_id'], grid['source_sha256']) == (doc_id, digest)
                             and grid.get('status') == 'PROPOSED_UNLABELED_AXIS_GRID']
                    beam_end_marker_pages.append(extract_pdf_beam_end_markers(
                        page, document_id=doc_id, page_number=number,
                        source_sha256=digest, source_name=path.name,
                        grid=grids[0] if len(grids) == 1 else None,
                    ))
                # Inventory the whole source page, including untitled details
                # and all vector/raster zones; indexing is NOT engineering approval.
                detail = inventory_pdf_page_regions(
                    page, document_id=doc_id, page_number=number,
                    sheet_kind=title_scope.get('sheet_kind'), include_topology=True,
                )
                detail["sheet_declarations"] = read_pdf_page_declarations(page)
                if axis_witness is not None:
                    detail["drawing_axis_witness"] = axis_witness
                if rendered_ocr and should_recover_rendered_labels(detail):
                    if ocr_attempts >= max_ocr_pages:
                        recovered = {
                            "document_id": doc_id, "page": number,
                            "status": "BLOCKED_OCR_PAGE_BUDGET",
                            "type_word_witness_count": 0, "type_word_witnesses": [],
                            "all_ocr_words_examined": False, "financially_payable": False,
                        }
                    else:
                        ocr_attempts += 1
                        recovered = recover_page_rendered_type_words(
                            page, document_id=doc_id, page_number=number,
                            native_witnesses=detail["type_word_index"]["type_word_witnesses"],
                            language=ocr_language, source_sha256=digest,
                        )
                    detail["rendered_type_word_index"] = recovered
                    rendered_ocr_pages.append({
                        "document_id": doc_id, "page": number, "status": recovered["status"],
                        "type_word_witness_count": recovered["type_word_witness_count"],
                        "ambiguous_glyph_count": recovered.get("ambiguous_glyph_count", 0),
                        "all_ocr_words_examined": recovered["all_ocr_words_examined"],
                        "source_quality": "RENDERED_OCR_NOT_VERIFIED",
                        "financially_payable": False,
                    })
                page_detail_summaries.append(detail)
                try:
                    marks, dims = _parse_pdf_lines(page)
                    if title_scope["sheet_kind"] == "floor_preparation_plan":
                        marks = [mark for mark in marks if not re.fullmatch(r"B[0-9]+", mark["tag"])]
                    grid = detect_vector_grid_positions(
                        page, document_id=doc_id, page_number=number, text_type_marks=marks,
                    )
                    symbols = compact_symbol_witness(page, grid['nodes'])
                    recognized = vector_column_type_labels(page, symbols['nodes'])
                except (RuntimeError, ValueError, MemoryError, KeyError, TypeError):
                    failure = "BLOCKED_LEGACY_PAGE_EXTRACTION"
                    detail["extraction_errors"].append(failure)
                    detail["coverage_status"] = "BLOCKED"
                    detail["status_counts"] = {"BLOCKED": len(detail["regions"])}
                    for region in detail["regions"]:
                        region.update(status="BLOCKED", reason="One or more PDF sheet readers did not complete.")
                    page_reasons.append({
                        "document_id": doc_id, "page": number, "status": failure,
                        "reason": "The sheet is retained, but its legacy text or grid extraction failed.",
                    })
                    continue
                grid_locations.extend(recognized['nodes'])
                if recognized['attached']:
                    vector_type_label_evidence.append({
                        'document_id': doc_id, 'page': number,
                        'attached': recognized['attached'],
                        'source_class': 'VECTOR_STROKE_LABEL',
                        'approval': 'PROPOSED_UNVERIFIED',
                    })
                if grid['status'] != 'NO_GRID_EVIDENCE':
                    vector_grid_summaries.append({
                        'document_id': doc_id, 'page': number,
                        'status': grid['status'],
                        'candidate_count': len(grid['nodes']),
                        'compact_symbol_candidates': symbols['symbol_candidate_count'],
                        'column_layout_symbol_candidates': symbols['column_context_candidates'],
                        'vector_label_attached_candidates': recognized['attached'],
                        'sheet_context': symbols['sheet_context'],
                        'axes_x_pt': grid['axes_x_pt'],
                        'levels_y_pt': grid['levels_y_pt'],
                        'member_count_verified': False,
                    })
                # Only source text is visible to this detector. Raster/SHX/path
                # encodings are NOT silently interpreted as absence of members.
                if not marks:
                    page_reasons.append({"document_id": doc_id, "page": number,
                                         "status": "BLOCKED_SEMANTIC_COVERAGE_UNKNOWN",
                                         "reason": "No independently identifiable member tags in searchable text; vector/raster inventory still needs review."})
                by_tag: dict[str, list[dict]] = defaultdict(list)
                for mark in marks:
                    by_tag[mark["tag"]].append(mark)
                for tag, occurrences in sorted(by_tag.items()):
                    # A repeated type name on one page does not prove extra
                    # *physical* members and must not be multiplied into BOQ.
                    candidate_pairs: list[tuple[float, dict, dict]] = []
                    for mark in occurrences:
                        candidates = [(score, dim) for dim in dims if (score := _score_pair(mark, dim)) is not None]
                        if candidates:
                            score, dim = min(candidates, key=lambda e: e[0])
                            candidate_pairs.append((score, mark, dim))
                    paired = sorted(candidate_pairs, key=lambda e: e[0])
                    if paired:
                        best_score, best_mark, best_dim = paired[0]
                        competing = [v for v in paired[1:] if (v[2]["quantity_kind"] != best_dim["quantity_kind"]
                                           or v[2]["quantity_m"] != best_dim["quantity_m"])]
                        # A second dimension very near the mark can also be a
                        # legitimate alternative even when there is one label.
                        same_mark_dims = sorted(
                            ((s, d) for d in dims if (s := _score_pair(best_mark, d)) is not None),
                            key=lambda x: x[0])
                        if len(same_mark_dims) > 1 and same_mark_dims[1][0] - same_mark_dims[0][0] < 5:
                            alternative = same_mark_dims[1][1]
                            if (alternative["quantity_m"], alternative["quantity_kind"]) != (
                                best_dim["quantity_m"], best_dim["quantity_kind"]):
                                competing.append((same_mark_dims[1][0], best_mark, alternative))
                        ambiguous = bool(competing)
                        record = {"tag": tag, "document_id": doc_id, "page": number,
                                  "mark_bbox_pt": best_mark["bbox"], "mark_text": best_mark["printed"],
                                  "dimension_bbox_pt": best_dim["bbox"], "dimension_text": best_dim["printed"],
                                  "dimension_kind": best_dim["quantity_kind"],
                                  "dimension_m": best_dim["quantity_m"],
                                  "status": "BLOCKED_MULTIPLE_DIMENSIONS" if ambiguous else "TYPE_DIMENSION_CANDIDATE",
                                  "confidence": "explicit_text_not_member_identity",
                                  "physical_instances_verified": False,
                                  "financially_payable": False}
                    else:
                        record = {"tag": tag, "document_id": doc_id, "page": number,
                                  "mark_bbox_pt": occurrences[0]["bbox"],
                                  "mark_text": occurrences[0]["printed"],
                                  "dimension_bbox_pt": None, "dimension_text": None,
                                  "dimension_kind": None, "dimension_m": None,
                                  "status": "BLOCKED_MISSING_DIMENSION",
                                  "confidence": "tag_only", "physical_instances_verified": False,
                                  "financially_payable": False}
                    raw_members.append(record)

    # Register source-backed column-layout grids against the *separate* axis
    # layout sheet, not against a floor plan.  Such a registration proves only
    # the positional witness in document coordinates, not physical members.
    registration = register_column_grid_against_axes(
        vector_grid_summaries, page_view_summaries,
    )
    accepted_grids = {
        (r['column_plan']['document_id'], r['column_plan']['page']): r
        for r in registration['column_plan_registrations']
        if r['status'] == 'PROPOSED_INDEPENDENT_GRID_REGISTRATION'
    }
    for node in grid_locations:
        reg = accepted_grids.get((node['document_id'], node['page']))
        if reg:
            node['independent_axis_grid_witness'] = {
                'axis_document_id': reg['axis_plan']['document_id'],
                'axis_page': reg['axis_plan']['page'],
                'axis_candidate_id': (
                    f"{reg['axis_plan']['document_id']}:p{reg['axis_plan']['page']}"
                    f":r{node['row']}:c{node['column']}"
                ),
                'max_residual_pt': reg['max_residual_pt'],
                'status': 'PROPOSED_INDEPENDENT_GRID_REGISTRATION',
                'physical_member_verified': False,
                'financially_payable': False,
            }

    grouped: dict[str, list[dict]] = defaultdict(list)
    for candidate in raw_members:
        grouped[candidate["tag"]].append(candidate)
    questions: list[dict] = []
    for tag, entries in sorted(grouped.items()):
        references = [v for v in entries if v["status"] == "TYPE_DIMENSION_CANDIDATE"]
        measures = {(v["dimension_kind"], v["dimension_m"]) for v in entries if v["dimension_m"]}
        has_conflicts = len(measures) > 1 or any(x["status"] == "BLOCKED_MULTIPLE_DIMENSIONS" for x in entries)
        if len(measures) == 1 and references and not has_conflicts:
            # A sheet with a tag but no dimension can reference a unique type
            # detail. This does NOT prove the number or identity of instances.
            source = references[0]
            for item in entries:
                if item["status"] == "BLOCKED_MISSING_DIMENSION":
                    item["status"] = "CROSS_VIEW_TYPE_REFERENCE_CANDIDATE"
                    item["type_reference"] = {
                        "document_id": source["document_id"], "page": source["page"],
                        "dimension_kind": source["dimension_kind"],
                        "dimension_m": source["dimension_m"],
                        "status": "PROPOSED_UNVERIFIED",
                    }
        if has_conflicts:
            for x in entries:
                x["status"] = "BLOCKED_CROSS_SHEET_CONFLICT"
            questions.append({"tag": tag, "status": "REVIEW_REQUIRED",
                              "question": "کدام مشخصات تیپ در نسخه حاکم نقشه معتبر است؟",
                              "suggestion": {"status": "PROPOSED_UNVERIFIED", "value": None,
                                             "reason": "تعارض شواهد؛ منبع حاکم بدون سند قابل تعیین نیست"},
                              "evidence": [{"document_id": e["document_id"], "page": e["page"],
                                            "dimension": e["dimension_m"], "kind": e["dimension_kind"]} for e in entries],
                              "options": ["confirm_document", "correct", "request_revised_sheet"]})
    # Tie a vector-read TYPE label to an unambiguous, text-backed type detail.
    # This is a *provisional reference to a dimension*, not a column instance,
    # replication factor, height, volume or accepted BOQ quantity.
    unique_type_details: dict[str, list[dict]] = {}
    for tag, entries in grouped.items():
        valid = [e for e in entries if e['status'] in
                 ('TYPE_DIMENSION_CANDIDATE', 'CROSS_VIEW_TYPE_REFERENCE_CANDIDATE')
                 and e.get('dimension_kind') and e.get('dimension_m')]
        distinct = {(e['dimension_kind'], e['dimension_m']) for e in valid}
        if len(distinct) == 1 and valid:
            unique_type_details[tag] = [
                {'document_id': e['document_id'], 'page': e['page'],
                 'dimension_kind': e['dimension_kind'],
                 'dimension_m': e['dimension_m'],
                 'status': 'PROPOSED_UNVERIFIED',
                 'source_class': 'PDF_TEXT_TYPE_DETAIL'}
                for e in valid]
    for node in grid_locations:
        tag = node.get('suggested_type')
        if (node.get('status') == 'GRID_LOCATION_VECTOR_TYPE_CANDIDATE' and
                tag in unique_type_details):
            node['cross_sheet_type_reference'] = {
                'tag': tag,
                'details': unique_type_details[tag],
                'status': 'PROPOSED_UNVERIFIED',
                'physical_member_verified': False,
                'quantity_approved': False,
            }

    # One review question per relevant *sheet*, never one interrupting modal
    # per individual grid node.  Column symbols may be clear as vector marks,
    # while their C1/C2/C3 annotation is outlined rather than searchable text.
    # A type candidate list from details does not establish per-node ownership.
    unresolved_column_grids: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for node in grid_locations:
        if node.get('column_context_candidate') and not node.get('type_verified'):
            unresolved_column_grids[(node['document_id'], node['page'])].append(node)
    known_types = sorted({e['tag'] for e in raw_members
                          if e['tag'].startswith('C') and
                          e['status'] in ('TYPE_DIMENSION_CANDIDATE',
                                          'CROSS_VIEW_TYPE_REFERENCE_CANDIDATE')})
    for (doc_id, page_no), nodes in sorted(unresolved_column_grids.items()):
        parsed_labels = [
            {'candidate_id': node['candidate_id'], 'type': node['suggested_type'],
             'status': 'PROPOSED_UNVERIFIED',
             'source_class': 'VECTOR_STROKE_LABEL',
             'bbox_pt': node.get('vector_type_label_evidence', {}).get('bbox_pt'),
             'cross_sheet_type_reference': node.get('cross_sheet_type_reference')}
            for node in nodes if node.get('suggested_type') and
            isinstance(node.get('vector_type_label_evidence'), dict)
        ]
        questions.append({
            'tag': f'GRID_TYPE:{doc_id}:p{page_no}',
            'status': 'REVIEW_REQUIRED',
            'question': 'انتساب تیپ‌های خوانده‌شده از علائم برداری این شیت برای متره معتبر است؟' if parsed_labels else 'تیپ‌های ستون در موقعیت‌های علامت‌دار این شیت چگونه تعیین می‌شوند؟',
            'suggestion': {
                'status': 'PROPOSED_UNVERIFIED',
                'value': None,
                'candidate_types_from_details': known_types,
                'per_location_type_candidates': parsed_labels,
                'reason': ('برچسب‌های برداری با هندسه قلم شناسایی شده‌اند؛ انتساب برای متره قطعی نیازمند بررسی مستقل اعتبار نقشه و نسخه آن است.'
                           if parsed_labels else
                           'وجود نماد و عنوان پلان ستون ثابت شد؛ تیپ تک‌تک موقعیت‌ها با شواهد متنی قابل اثبات نیست.')
            },
            'evidence': [
                {'document_id': node['document_id'], 'page': node['page'],
                 'candidate_id': node['candidate_id'],
                 'x_pt': node['x_pt'], 'y_pt': node['y_pt'],
                 'symbol_status': node['symbol_status'],
                 'vector_type_candidate': node.get('suggested_type'),
                 'label_provenance': node.get('vector_type_label_evidence')}
                for node in nodes
            ],
            'options': ['confirm_suggestion', 'correct', 'request_document'],
            'financially_payable': False,
        })
    # Independent architectural floor titles are an inventory of available
    # drawings, NOT proof that the single column type layout is repeated over
    # those floors. Raise one grouped *end-user* question where the reference
    # structure and floor sheets coexist but no level/stacking authority does.
    architectural_floor_sheets = [
        {'document_id': view['document_id'], 'page': view['page'],
         'sheet_kind': view['sheet_kind']}
        for view in page_view_summaries
        if view['status'] == 'EXPLICIT_SHEET_TITLE'
        and view['sheet_kind'] in (
            'pilot_floor_plan', 'ground_floor_plan', 'first_floor_plan',
        )
    ]
    if registration['registered_grid_positions'] and architectural_floor_sheets:
        questions.append({
            'tag': 'COLUMN_FLOOR_SCOPE',
            'status': 'REVIEW_REQUIRED',
            'question': 'برای برآورد ستون‌های این پلان، هر تیپ در کدام طبقات و ترازهای واقعی اجرا شده است؟',
            'suggestion': {
                'status': 'PROPOSED_UNVERIFIED',
                'value': None,
                'floor_plan_candidates': architectural_floor_sheets,
                'reason': ('پلان‌های معماری این ترازها در مجموعه موجودند، '
                           'ولی از حضور پلان، تکرار ستون و طول اجرایی در هر تراز اثبات نمی‌شود.'),
            },
            'evidence': [
                {'document_id': r['column_plan']['document_id'],
                 'page': r['column_plan']['page'],
                 'axis_page': r['axis_plan']['page'],
                 'registered_positions': r['supported_positions']}
                for r in registration['column_plan_registrations']
                if r['status'] == 'PROPOSED_INDEPENDENT_GRID_REGISTRATION'
            ] + architectural_floor_sheets,
            'options': ['confirm_suggestion', 'correct', 'request_document'],
            'financially_payable': False,
        })

    status_counts = Counter(x["status"] for x in raw_members)
    report = {"documents": documents, "page_count": total_pages,
            "rendered_ocr_enabled": rendered_ocr,
            "rendered_ocr_language": ocr_language if rendered_ocr else None,
            "rendered_ocr_page_index": rendered_ocr_pages,
            "rendered_ocr_candidate_count": sum(x["type_word_witness_count"] for x in rendered_ocr_pages),
            "rendered_ocr_ambiguous_glyph_count": sum(x["ambiguous_glyph_count"] for x in rendered_ocr_pages),
            "member_type_candidates": raw_members,
            "page_view_summaries": page_view_summaries,
            "architectural_floor_plan_candidates": architectural_floor_sheets,
            "independent_axis_grid_registrations": registration['column_plan_registrations'],
            "independently_registered_grid_positions": registration['registered_grid_positions'],
            "floor_repetition_multiplier": None,
            "floor_repetition_verified": False,
            "grid_location_candidates": grid_locations,
            "vector_type_label_evidence": vector_type_label_evidence,
            "vector_type_detail_link_count": sum(
                bool(node.get("cross_sheet_type_reference")) for node in grid_locations),
            "vector_type_label_candidate_count": sum(
                node.get("status") == "GRID_LOCATION_VECTOR_TYPE_CANDIDATE"
                for node in grid_locations),
            "compact_symbol_candidate_count": sum(x["symbol_status"] == "COMPACT_VECTOR_SYMBOL_CANDIDATE" for x in grid_locations),
            "column_layout_symbol_candidate_count": sum(bool(x["column_context_candidate"]) for x in grid_locations),
            "vector_grid_summaries": vector_grid_summaries,
            "beam_axis_grid_candidates": beam_axis_grid_candidates,
            "beam_end_marker_pages": beam_end_marker_pages,
            "questions": questions, "unresolved_pages": page_reasons,
            "status_counts": dict(sorted(status_counts.items())),
            "physical_member_count": None, "quantity_approval_count": 0,
            "complete": False, "acceptance": "PARTIAL_NO_GO",
            "source_type": "PDF_ONLY", "excel_required": False}
    report["column_position_ledger"] = compile_column_position_ledger(report)
    report["sheet_detail_inventory"] = assemble_pdf_detail_inventory(
        page_detail_summaries, documents,
    )
    # Explicit detail titles and member-type labels are kept as separate,
    # non-payable source candidates. Untitled geometry remains unresolved.
    report["detail_object_index"] = build_pdf_detail_object_index(
        report["sheet_detail_inventory"],
    )
    report["multidiscipline_gap_register"] = build_pdf_multidiscipline_gap_register(
        report["sheet_detail_inventory"], report["detail_object_index"],
    )
    report["operator_component_review"] = build_pdf_operator_component_review(
        page_detail_summaries, report["sheet_detail_inventory"],
        report["detail_object_index"], report["member_type_candidates"],
    )
    graph = build_pdf_detail_evidence_graph(
        report, page_detail_summaries, revision_registry=revision_registry, member_review=member_review,
        beam_profile_witnesses=beam_profile_witnesses, beam_axis_labels=beam_axis_labels,
        beam_detail_profile_witnesses=beam_detail_profile_witnesses,
    )
    report["detail_evidence_graph"] = graph
    report["questions"].extend(graph["review_questions"])
    for path, document in zip(received, documents, strict=True):
        require_current_pdf(path, document["sha256"])
    # Every page/zone must be accounted for, but unresolved drawing geometry
    # must never be silently promoted to complete member takeoff or BOQ.
    return report
