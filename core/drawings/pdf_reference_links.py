"""Source-localized review receipts for the existing PDF evidence graph."""


_REVISION_REASONS = {
    "REVISION_CONFLICT", "SUPERSEDED_SOURCE", "UNVERIFIED_DOCUMENT_SCOPE",
    "DIFFERENT_PROJECT_OR_ISSUE", "DUPLICATE_CURRENT_SHEET_ID",
}
_CONFLICT_REASONS = {
    "AMBIGUOUS_REFERENCE_TARGET", "CONFLICTING_SOURCE_SHEET_IDS",
    "SELF_SHEET_REFERENCE", "TYPE_FAMILY_CONFLICT", "CONFLICTING_DETAIL_REFERENCES",
    "BLOCKED_PRINTED_MEMBER_COUNT_CONFLICT", "BLOCKED_PRINTED_MEMBER_ID_CONFLICT",
}
_PROJECTED_EDGES = {
    "PRINTED_SHEET_REFERENCE": "SHEET_REFERENCE",
    "DETAIL_CALLOUT": "PLAN_TO_DETAIL",
    "SCHEDULE_DETAIL_CALLOUT": "TYPE_TO_DETAIL",
    "INSTANCE_TYPE_CANDIDATE": "PLAN_TO_TYPE",
    "COLUMN_DETAIL_TYPE_REFERENCE": "PLAN_TO_TYPE",
    "DETAIL_TYPE_DEFINITION": "TYPE_TO_DETAIL",
    "PLAN_DETAIL_PRINTED_MEMBER_ID": "PLAN_TO_DETAIL",
    "PRINTED_SCHEDULE_CONFLICT": "PLAN_TO_DETAIL",
}
_LITERAL_KINDS = {
    "PRINTED_SHEET_REFERENCE": "SHEET_REFERENCE",
    "DETAIL_CALLOUT": "CALLOUT",
    "SCHEDULE_DETAIL_CALLOUT": "SCHEDULE_ROW",
}


def _page_key(anchor):
    return anchor.get("document_id"), anchor.get("page")


def _anchors(node, pages):
    return [anchor for anchor in node["anchors"]
            if anchor.get("anchor_id") and anchor.get("bbox_pt") and _page_key(anchor) in pages]


def _target_location(node, pages):
    if not node:
        return None
    anchors = _anchors(node, pages)
    if len({_page_key(anchor) for anchor in anchors}) != 1:
        return None
    # Prefer the printed destination to an entire sheet or a supporting vector group.
    for kind in ("DETAIL_TITLE", "SHEET_ID"):
        for anchor in anchors:
            if anchor["kind"] == kind:
                return anchor
    return anchors[0]


def _state(status, reason):
    if (reason in _CONFLICT_REASONS or (reason or "").endswith("_PRINTED_SCHEDULE_CONFLICT")
            or status in {"AMBIGUOUS", "REJECTED", "CONFLICTED"}):
        return "CONFLICTED"
    if reason in _REVISION_REASONS:
        return "BLOCKED_REVISION"
    if reason == "REFERENCE_TARGET_NOT_FOUND" or status == "BLOCKED":
        return "BLOCKED_MISSING_DOCUMENT"
    if status == "VALIDATED_REFERENCE":
        return "SOURCE_SUPPORTED"
    return "CANDIDATE"


def _evidence(anchors, pages):
    evidence = {}
    for anchor in anchors:
        key = _page_key(anchor)
        if key in pages and anchor.get("bbox_pt") and anchor.get("anchor_id"):
            digest = pages[key]["sha256"]
            if anchor.get("source_sha256", digest) != digest:
                raise ValueError("Foreign PDF reference witness")
            evidence[anchor["anchor_id"]] = {**anchor, "source_sha256": digest}
    return list(evidence.values())


def _reference_row(link_id, link_type, primary, target, target_node, anchors, pages, *,
                   status, reason=None, reference_text=None, candidates=(), edge_id=None):
    source_key = _page_key(primary)
    source_page = pages[source_key]
    target_key = _page_key(target) if target else None
    target_page = pages.get(target_key)
    verification = _state(status, reason)
    revisions = [source_page["authority_status"]]
    if target_page is not None:
        revisions.append(target_page["authority_status"])
    revision_status = reason if reason in _REVISION_REASONS else (
        "CURRENT" if all(r == "CURRENT" for r in revisions) else next(r for r in revisions if r != "CURRENT")
    )
    return {
        "link_id": link_id, "graph_edge_id": edge_id, "link_type": link_type,
        "source_document_id": source_key[0], "source_sheet": source_key[1],
        "source_sheet_code": source_page["sheet_id"] or "UNKNOWN",
        "source_bbox": primary["bbox_pt"], "source_anchor_id": primary["anchor_id"],
        "source_operator_ids": list(primary.get("source_operator_ids", ())),
        "target_document_id": target_key[0] if target_key else "UNKNOWN",
        "target_sheet": target_key[1] if target_key else "UNKNOWN",
        "target_sheet_code": primary.get("sheet") or (target_page and target_page["sheet_id"]) or "UNKNOWN",
        "target_bbox": target["bbox_pt"] if target and verification in {"SOURCE_SUPPORTED", "CANDIDATE"} else None,
        "target_node_id": target_node if verification == "SOURCE_SUPPORTED" else None,
        "reference_text": reference_text or primary.get("printed") or primary.get("raw_token") or "UNKNOWN",
        "revision_status": revision_status, "verification_state": verification, "reason_code": reason,
        "evidence": _evidence(anchors, pages), "candidate_targets": list(candidates),
        # These are observations. Even circular mutual references carry no dependency semantics.
        "engineering_dependency": False, "physical_member_verified": False,
        "quantity_approved": False, "financially_payable": False,
    }


def build_reference_links(nodes, edges, pages, scope_disagreement):
    """Project stated links and existing bounded review candidates, never proximity-only edges."""
    links = []
    for edge in edges:
        relationship = edge["relationship"]
        link_type = _PROJECTED_EDGES.get(relationship)
        if not link_type:
            continue
        source = nodes[edge["source_id"]]
        target_node = nodes.get(edge["target_id"])
        primary_anchors = (_anchors(source, pages) if relationship not in _LITERAL_KINDS else [
            anchor for anchor in edge["anchors"] if anchor["kind"] == _LITERAL_KINDS[relationship]
        ])
        if relationship == "DETAIL_TYPE_DEFINITION":
            primary_anchors = [a for a in primary_anchors if a["kind"] == "DETAIL_TITLE"]
            target_node = source
        elif relationship in {"PLAN_DETAIL_PRINTED_MEMBER_ID", "PRINTED_SCHEDULE_CONFLICT"}:
            local_pages = {_page_key(a) for a in primary_anchors}
            primary_anchors = [a for a in edge["anchors"] if a["kind"] == "VISUALLY_READ_PLAN_MEMBER_ID"
                               and _page_key(a) in local_pages][:1] or primary_anchors[:1]
        elif relationship not in _LITERAL_KINDS:
            # Retain one record per actual source page, with additional witnesses in evidence.
            per_page = {}
            for anchor in primary_anchors:
                key = _page_key(anchor)
                if key not in per_page or anchor["kind"] == "COLUMN_PLAN_GLYPH":
                    per_page[key] = anchor
            primary_anchors = list(per_page.values())
        target = _target_location(target_node, pages)
        for primary in primary_anchors:
            source_page = pages[_page_key(primary)]
            emitted_type = link_type
            reference_kind = primary.get("reference")
            if relationship == "DETAIL_CALLOUT":
                if source_page["page_role"] in {"SECTION", "ELEVATION"}:
                    emitted_type = "SECTION_TO_DETAIL" if reference_kind in {"DETAIL", "دیتیل"} else "SHEET_REFERENCE"
                elif source_page["page_role"] in {"PLAN", "AXIS_PLAN"}:
                    emitted_type = ("PLAN_TO_SECTION" if reference_kind in {"SECTION", "ELEVATION", "مقطع", "نما"}
                                    else link_type)
                else:
                    emitted_type = "SHEET_REFERENCE"
            reason = edge["reason_code"]
            if edge["status"] == "PROPOSED" and reason is None and target and _page_key(primary) != _page_key(target):
                reason = scope_disagreement(source_page, pages[_page_key(target)])
            candidate_targets = []
            for candidate_id in edge["candidate_ids"]:
                candidate_node = nodes[candidate_id]
                candidate_anchors = _anchors(candidate_node, pages)
                candidate_location = _target_location(candidate_node, pages)
                candidate_page = pages[_page_key(candidate_location)] if candidate_location else None
                candidate_targets.append({
                    "node_id": candidate_id,
                    "scope_reason": scope_disagreement(source_page, candidate_page) if candidate_page else None,
                    "evidence": _evidence(candidate_anchors, pages),
                })
            links.append(_reference_row(
                f'{edge["edge_id"]}:{primary["anchor_id"]}', emitted_type, primary, target,
                target_node["node_id"] if target_node else None,
                [primary, *edge["anchors"], *(target_node["anchors"] if target_node else ())], pages,
                status=edge["status"], reason=reason, candidates=candidate_targets, edge_id=edge["edge_id"],
                reference_text=primary.get("printed") or primary.get("raw_token") or source.get("label"),
            ))

    for page in pages.values():
        for revision in page["anchors_by_kind"]["REVISION"]:
            reason = page["authority_block"] or (None if page["authority"] else "UNVERIFIED_DOCUMENT_SCOPE")
            links.append(_reference_row(
                f'REVISION:{revision["anchor_id"]}', "REVISION_REFERENCE", revision, revision,
                None, [revision], pages, status="VALIDATED_REFERENCE", reason=reason,
            ))
    if len({row["link_id"] for row in links}) != len(links):
        raise ValueError("Duplicate PDF reference receipt")
    return links
