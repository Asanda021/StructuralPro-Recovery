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
from typing import Iterable

from core.drawings.pdf_grid_instances import detect_vector_grid_positions
from core.drawings.pdf_vector_symbol_witness import compact_symbol_witness
from core.drawings.pdf_vector_type_labels import vector_column_type_labels


_MEMBER_MARK = re.compile(
    r"(?<![A-Za-z0-9])(?P<family>SC|SW|C|B|W|F|P|S)\s*[-–]?\s*(?P<index>[1-9][0-9]{0,2})(?![A-Za-z0-9])",
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
    received = [Path(item) for item in paths]
    if not received or len(received) > max_documents or max_pages < 1:
        raise ValueError("PDF intake requires a bounded, nonempty set of sheets")
    if len({str(p.resolve()) for p in received}) != len(received):
        raise ValueError("Duplicate PDF source selection is not allowed")
    documents: list[dict] = []
    raw_members: list[dict] = []
    grid_locations: list[dict] = []
    vector_type_label_evidence: list[dict] = []
    vector_grid_summaries: list[dict] = []
    page_reasons: list[dict] = []
    total_pages = 0
    for path in received:
        if path.suffix.lower() != ".pdf" or not path.is_file():
            raise ValueError("Every selected drawing must be an existing PDF")
        data = path.read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.is_repaired or not doc.is_pdf or not len(doc):
                raise ValueError("PDF source is unreadable, repaired or encrypted")
            total_pages += len(doc)
            if total_pages > max_pages:
                raise ValueError("PDF page-count limit exceeded")
            doc_id = f"PDF{len(documents) + 1:03d}"
            documents.append({"document_id": doc_id, "page_count": len(doc),
                              "source_name": path.name, "sha256": sha256(data).hexdigest()})
            for number, page in enumerate(doc, 1):
                marks, dims = _parse_pdf_lines(page)
                grid = detect_vector_grid_positions(
                    page, document_id=doc_id, page_number=number,
                    text_type_marks=marks,
                )
                symbols = compact_symbol_witness(page, grid['nodes'])
                recognized = vector_column_type_labels(page, symbols['nodes'])
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
    status_counts = Counter(x["status"] for x in raw_members)
    return {"documents": documents, "page_count": total_pages,
            "member_type_candidates": raw_members,
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
            "questions": questions, "unresolved_pages": page_reasons,
            "status_counts": dict(sorted(status_counts.items())),
            "physical_member_count": None, "quantity_approval_count": 0,
            "complete": False, "acceptance": "PARTIAL_NO_GO",
            "source_type": "PDF_ONLY", "excel_required": False}