"""Auditable, non-authoritative local PDF component/title/type references."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import pairwise

from core.drawings.pdf_detail_topology import _Stroke, _bounds, _cross, _inside_bounds, _non_endpoint_contact
from core.drawings.pdf_type_word_witness import pdf_type_mark_family

_TITLE_GAP_PT = 36.0
_LOCAL_PAIR_BUDGET = 1_200_000
_LOCAL_TYPE_METHODS = {"NATIVE_TYPE_WORD", "VECTOR_STROKE_LABEL"}
_REVIEWABLE_BOUNDARY_ROLES = {"CLOSED_OUTLINE", "ENCLOSING_OUTLINE_REVIEW"}
_ENGINEERING_EVIDENCE = ("GOVERNING_REVISION", "PLAN_AXIS_AND_LEVEL", "SECTION_AND_SUPPORT_REFERENCE",
                         "INDEPENDENT_BOUNDARY_AND_DIMENSIONS")
_REVIEW_EVIDENCE = {
    "NO_LOCAL_DETAIL_TITLE": "EXPLICIT_LOCAL_DETAIL_TITLE_WITH_TYPE",
    "NO_EXPLICIT_TYPE_WORD_IN_TITLE": "EXPLICIT_LOCAL_DETAIL_TITLE_WITH_TYPE",
    "MULTIPLE_LOCAL_DETAIL_TITLES": "UNIQUE_TITLE_AND_DRAWING_SCOPE",
    "TITLE_NEAR_MULTIPLE_OUTLINES": "UNIQUE_TITLE_AND_DRAWING_SCOPE",
    "MULTIPLE_SCALE_SCOPES": "SCALE_SCOPE_OF_THIS_DETAIL",
    "NO_APPLICABLE_LOCAL_SCALE": "SCALE_SCOPE_OF_THIS_DETAIL",
    "MULTIPLE_LOCAL_SCALE_WITNESSES": "SCALE_SCOPE_OF_THIS_DETAIL",
    "SCALE_PRINT_OUTSIDE_LOCAL_VIEW": "SCALE_SCOPE_OF_THIS_DETAIL",
    "SAME_TYPE_ON_OTHER_SHEET": "ISSUED_SHEET_AND_DETAIL_ID",
    "SAME_TYPE_IN_OTHER_DOCUMENT": "ISSUED_SHEET_AND_DETAIL_ID",
    "NO_INDEPENDENT_TYPE_INSIDE_OUTLINE": "INDEPENDENT_TYPE_WORD_IN_OUTLINE",
    "OCR_ONLY_TYPE_IN_OUTLINE": "INDEPENDENT_TYPE_WORD_IN_OUTLINE",
    "AMBIGUOUS_GLYPH_IN_OUTLINE": "INDEPENDENT_GLYPH_AND_TYPE_REVIEW",
}


def _near_title(outline_box, title_box):
    a, b, c, d = outline_box
    x, y, u, v = title_box
    return min(c, u) > max(a, x) and max(0, b - v, y - d) <= _TITLE_GAP_PT


def _point_inside(point, poly_edges):
    x, y = point
    crossed = False
    for edge in poly_edges:
        a, b = edge.start, edge.end
        if _cross(a, b, point) == 0 and _inside_bounds(edge.box, point):
            return False
        if (a[1] > y) != (b[1] > y):
            crossed ^= x < a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
    return crossed


def _word_inside(word_box, outline_box, poly_edges):
    x, y, u, v = word_box
    a, b, c, d = outline_box
    if not (a < x < u < c and b < y < v < d):
        return False
    corners = ((x, y), (u, y), (u, v), (x, v))
    if not all(_point_inside(point, poly_edges) for point in corners):
        return False
    box_edges = [_Stroke(i, p, q, _bounds((p, q))) for i, (p, q) in enumerate(pairwise((*corners, corners[0])))]
    return not any(_non_endpoint_contact(p, q) for p in poly_edges for q in box_edges)


def _local_context(boundary, titles, words):
    box = boundary["bbox_pt"]
    if boundary["classification_status"] == "NON_MEMBER" or box is None:
        return (), ()
    nearby = [title for title in titles if _near_title(box, title["bbox_pt"])]
    if boundary["boundary_role"] not in _REVIEWABLE_BOUNDARY_ROLES:
        return nearby, ()
    outline = tuple(map(tuple, boundary["outline_pt"]))
    sides = [_Stroke(i, a, b, _bounds((a, b))) for i, (a, b) in enumerate(pairwise((*outline, outline[0])))]
    return (nearby,
            [word for word in words if not word["title_anchor_ids"] and _word_inside(word["bbox_pt"], box, sides)])


def _choose_link(boundary, titles, local_words, title_words, nearby_owners, word_owners,
                 tag_pages, scope, local_scales, budget_exceeded):
    """Return a single disposition, without selecting nearest competitors."""
    role, state = boundary["boundary_role"], boundary["classification_status"]
    if state == "NON_MEMBER":
        return "EXCLUDED_NON_MEMBER", boundary["reason_code"], None, None, None
    if state == "BLOCKED":
        return "BLOCKED", boundary["reason_code"], None, None, None
    if budget_exceeded:
        return "BLOCKED", "BOUNDARY_LINK_COMPARISON_BUDGET", None, None, None
    if role not in _REVIEWABLE_BOUNDARY_ROLES:
        return "UNRESOLVED", "NO_ELIGIBLE_CLOSED_BOUNDARY", None, None, None
    if state != "CANDIDATE":
        return "BLOCKED", boundary["reason_code"], None, None, None
    if scope["authority_status"] in {"REVISION_CONFLICT", "SUPERSEDED_SOURCE", "DUPLICATE_CURRENT_SHEET_ID"}:
        return "BLOCKED", scope["authority_status"], None, None, None
    if not titles:
        return "UNRESOLVED", "NO_LOCAL_DETAIL_TITLE", None, None, None
    if len(titles) > 1:
        return "BLOCKED", "MULTIPLE_LOCAL_DETAIL_TITLES", None, None, None
    title, = titles
    title_id = title["title_anchor_id"]
    if nearby_owners[title_id] > 1:
        return "BLOCKED", "TITLE_NEAR_MULTIPLE_OUTLINES", title, None, None
    if title["status"].startswith("BLOCKED") or title["family_basis"] != "EXPLICIT_NATIVE_TITLE_FAMILY":
        return "BLOCKED", "TITLE_FAMILY_OR_SOURCE_UNVERIFIED", title, None, None
    if not scope["examined"]:
        return "BLOCKED", "PAGE_DECLARATION_SOURCE_INCOMPLETE", title, None, None
    if len(scope["scale_values"]) > 1:
        return "BLOCKED", "MULTIPLE_SCALE_SCOPES", title, None, None
    title_type = title_words[title_id]
    if len(title_type) != 1:
        reason = "MULTIPLE_TYPE_WORDS_IN_DETAIL_TITLE" if title_type else "NO_EXPLICIT_TYPE_WORD_IN_TITLE"
        return ("BLOCKED" if title_type else "UNRESOLVED"), reason, title, None, None
    declared, = title_type
    tag = declared["type_tag"]
    family, _ = pdf_type_mark_family(tag, boundary["sheet_kind"])
    if not family or family not in title["family_candidates"]:
        return "BLOCKED", "TITLE_AND_TYPE_FAMILY_CONFLICT", title, declared, None
    if len(tag_pages[tag, family]) > 1:
        elsewhere = any(doc != boundary["document_id"] for doc, _ in tag_pages[tag, family])
        reason = "SAME_TYPE_IN_OTHER_DOCUMENT" if elsewhere else "SAME_TYPE_ON_OTHER_SHEET"
        return "BLOCKED", reason, title, declared, None
    if any(word["status"] in {"AMBIGUOUS_GLYPH", "UNRESOLVED_VECTOR_STROKE_MARK"} for word in local_words):
        return "BLOCKED", "AMBIGUOUS_GLYPH_IN_OUTLINE", title, declared, None
    trusted = [word for word in local_words if word["method"] in _LOCAL_TYPE_METHODS and word["type_tag"]]
    if not trusted:
        ocr_only = any(word["method"] == "RENDERED_OCR" for word in local_words)
        reason = "OCR_ONLY_TYPE_IN_OUTLINE" if ocr_only else "NO_INDEPENDENT_TYPE_INSIDE_OUTLINE"
        return "UNRESOLVED", reason, title, declared, None
    if len(trusted) > 1 or word_owners[trusted[0]["source_id"]] > 1:
        return "BLOCKED", "COMPETING_LOCAL_TYPE_OR_BOUNDARY_OWNERS", title, declared, None
    matched, = trusted
    if matched["type_tag"] != tag:
        return "BLOCKED", "LOCAL_TYPE_CONFLICTS_WITH_TITLE", title, declared, matched
    if len(local_scales) > 1:
        return "BLOCKED", "MULTIPLE_LOCAL_SCALE_WITNESSES", title, declared, matched
    if not local_scales or tuple(local_scales[0]["direction"]) != (1, 0):
        return "UNRESOLVED", "NO_APPLICABLE_LOCAL_SCALE", title, declared, matched
    if scope["scale_owners"][local_scales[0]["source_line"], local_scales[0]["part"]] > 1:
        return "BLOCKED", "MULTIPLE_SCALE_SCOPES", title, declared, matched
    a, _, c, _ = boundary["bbox_pt"]
    x, _, u, _ = local_scales[0]["bbox_pt"]
    if not a <= x < u <= c:
        return "UNRESOLVED", "SCALE_PRINT_OUTSIDE_LOCAL_VIEW", title, declared, matched
    if scope["authority_status"] != "CURRENT":
        return "BLOCKED", "LOCAL_DETAIL_REVISION_UNVERIFIED", title, declared, matched
    return "PROPOSED", "UNIQUE_TYPED_TITLE_AND_DISTINCT_WORD_INSIDE_OUTLINE", title, declared, matched


def build_pdf_component_source_links(boundaries, title_rows, witnesses, summaries, page_sources,
                                     *, page_authority=None):
    """Record what can and cannot be traced without granting member authority."""
    by_page, titles, words = defaultdict(list), defaultdict(list), defaultdict(list)
    boundary_ids, title_pages, word_ids = set(), {}, set()
    for row in boundaries:
        key = row["document_id"], row["page"]
        ident = row["component_id"]
        prefix = f"{key[0]}:p{key[1]}:"
        if (key not in page_sources or row["source_pdf_sha256"] != page_sources[key]
                or ident in boundary_ids or not ident.startswith(prefix + "boundary")
                or any(not ref.startswith(prefix + "d") for ref in row["source_operator_ids"])
                or row.get("financially_payable") is not False or row.get("physical_member_count") is not None):
            raise ValueError("Foreign, duplicate or promoted boundary link origin")
        boundary_ids.add(ident)
        by_page[key].append(row)
    for row in title_rows:
        key = row["document_id"], row["page"]
        ident = row["title_anchor_id"]
        if (key not in page_sources or row["source_pdf_sha256"] != page_sources[key]
                or ident in title_pages or row.get("financially_payable") is not False):
            raise ValueError("Foreign, duplicate or promoted component title evidence")
        title_pages[ident] = key
        titles[key].append(row)

    title_words, tag_pages = defaultdict(list), defaultdict(set)
    for word in witnesses:
        key = word["document_id"], word["page"]
        ident = word["source_id"]
        if (key not in page_sources or word["source_pdf_sha256"] != page_sources[key]
                or ident in word_ids or word.get("financially_payable") is not False):
            raise ValueError("Foreign, duplicate or promoted component type evidence")
        word_ids.add(ident)
        words[key].append(word)
        tag = word["type_tag"]
        if not tag or word["method"] not in _LOCAL_TYPE_METHODS:
            continue
        family, _ = pdf_type_mark_family(tag, summaries[key]["sheet_kind"])
        if family:
            tag_pages[tag, family].add(key)
        for anchor in word["title_anchor_ids"]:
            if anchor in title_pages and title_pages[anchor] != key:
                raise ValueError("Foreign title reference in a PDF type word")
            title_words[anchor].append(word)

    links = []
    for key, rows in by_page.items():
        local_titles, local_words = titles[key], words[key]
        comparable = sum(row["boundary_role"] in _REVIEWABLE_BOUNDARY_ROLES for row in rows)
        declarations = summaries[key].get("sheet_declarations") or {}
        scales = [item for item in declarations.get("declarations", ()) if item.get("kind") == "PRINTED_SCALE"]
        budget_exceeded = (len(rows) * len(local_titles) + comparable * (len(local_words) + len(scales))
                           > _LOCAL_PAIR_BUDGET)
        if budget_exceeded:
            contexts = [((), ())] * len(rows)
        else:
            contexts = [_local_context(row, local_titles, local_words) for row in rows]
        title_owners = Counter(t["title_anchor_id"] for row, (possible, _) in zip(rows, contexts, strict=True)
                               if row["boundary_role"] in _REVIEWABLE_BOUNDARY_ROLES for t in possible)
        word_owners = Counter(w["source_id"] for _, contained in contexts for w in contained)
        scale_matches = {} if budget_exceeded else {
            row["component_id"]: [scale for scale in scales if _near_title(row["bbox_pt"], scale["bbox_pt"])]
            for row in rows if row["boundary_role"] in _REVIEWABLE_BOUNDARY_ROLES
        }
        scope = {
            "examined": declarations.get("status") == "EXAMINED",
            "scale_values": sorted({item["denominator"] for item in scales}),
            "scale_owners": Counter((scale["source_line"], scale["part"])
                                    for local in scale_matches.values() for scale in local),
            "authority_status": (page_authority or {}).get(key, "UNREGISTERED"),
        }
        for row, (possible, contained) in zip(rows, contexts, strict=True):
            local_scales = scale_matches.get(row["component_id"], [])
            status, reason, title, declared, matched = _choose_link(
                row, possible, contained, title_words, title_owners, word_owners,
                tag_pages, scope, local_scales, budget_exceeded,
            )
            request = _REVIEW_EVIDENCE.get(reason)
            required = [request] if request else []
            if status != "EXCLUDED_NON_MEMBER":
                required.extend(_ENGINEERING_EVIDENCE)
            scale_scope = None
            if status == "PROPOSED":
                boxes = (row["bbox_pt"], local_scales[0]["bbox_pt"], title["bbox_pt"])
                scale_scope = list(_bounds([point for box in boxes for point in (box[:2], box[2:])]))
            links.append({
                "link_id": f'SOURCE_LINK:{row["component_id"]}', "component_id": row["component_id"],
                "document_id": key[0], "page": key[1], "source_pdf_sha256": page_sources[key],
                "bbox_pt": row["bbox_pt"], "sheet_kind": row["sheet_kind"],
                "scope": "SAME_DOCUMENT_PAGE_ONLY", "boundary_role": row["boundary_role"],
                "source_operator_ids": row["source_operator_ids"], "source_paths": row["source_paths"],
                "outline_pt": row["outline_pt"],
                "competing_context_operator_ids": row.get("competing_context_operator_ids", ()),
                "competing_context_bbox_pt": row.get("competing_context_bbox_pt"),
                "title_anchor_id": title["title_anchor_id"] if title else None,
                "title_bbox_pt": title["bbox_pt"] if title else None,
                "title_text": title["title_preview"] if title else None,
                "nearby_title_witnesses": [
                    {"anchor_id": t["title_anchor_id"], "bbox_pt": t["bbox_pt"], "source_token": t["title_preview"]}
                    for t in possible
                ],
                "type_tag": declared["type_tag"] if declared else None, "title_type_source": declared,
                "family_candidates": title["family_candidates"] if title else (),
                "type_source": matched, "local_type_witnesses": list(contained),
                "printed_scale_denominators": scope["scale_values"],
                "local_printed_scale_witnesses": local_scales,
                "authority_status": scope["authority_status"],
                "scale_scope_bbox_pt": scale_scope,
                "scale_calibrated": False, "independently_reviewed": False,
                "status": status, "reason_code": reason,
                "required_evidence": required,
                "detail_boundary_verified": False, "span_specific_detail_verified": False,
                "physical_member_verified": False, "physical_member_count": None,
                "quantity_approval_count": 0, "financially_payable": False,
            })
    return links
