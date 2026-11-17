"""Per-sheet, all-trade PDF coverage gaps. Not a detail classifier or BOQ.

A detected title/type mark establishes a *search lead*, not complete discipline
scope. Always retain an unclassified remainder for each page so an unrelated
trade cannot be silently declared absent or processed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FAMILIES = frozenset((
    "bracing", "beam", "column", "foundation", "slab_roof", "wall_opening",
    "stair_ramp", "reinforcement_connection", "architecture_finishes",
    "mechanical", "electrical",
))
_MAX_PAGES = 600
_MAX_OBJECTS = 20000


def build_pdf_multidiscipline_gap_register(coverage: Mapping, detail_index: Mapping) -> dict:
    """Account for every page, every visual zone, and *unidentified* trades.

    This ledger never infers missing trades from absent text; family hypotheses
    simply prioritize human review. It doesn't join different sheets, levels,
    drawing revisions or spans, and it cannot approve physical quantities.
    """
    if (not isinstance(coverage, Mapping) or coverage.get("all_input_pages_indexed") is not True
            or coverage.get("errors") or coverage.get("acceptance") != "PARTIAL_NO_GO"
            or coverage.get("quantity_approval_count") != 0
            or not isinstance(detail_index, Mapping)
            or detail_index.get("acceptance") != "PARTIAL_NO_GO"
            or detail_index.get("physical_member_count") is not None
            or detail_index.get("quantity_approval_count") != 0
            or detail_index.get("complete") is not False):
        raise ValueError("A complete, nonfinancial source inventory and unresolved detail index are required")
    docs = coverage.get("documents")
    pages = coverage.get("sheet_inventory")
    regions = coverage.get("region_inventory")
    candidates = detail_index.get("detail_candidates")
    unknown_visual = detail_index.get("unassigned_visual_regions")
    if (not isinstance(docs, list) or not docs or
            not isinstance(pages, list) or not 1 <= len(pages) <= _MAX_PAGES or
            not isinstance(regions, list) or not isinstance(candidates, list)
            or len(candidates) > _MAX_OBJECTS or
            not isinstance(unknown_visual, list)):
        raise ValueError("Missing or unbounded PDF coverage evidence")
    doc_hashes = {}
    expected = set()
    for d in docs:
        ident, digest, count = d.get("document_id"), d.get("sha256"), d.get("page_count")
        if (not isinstance(ident, str) or not ident or ident in doc_hashes or
                not isinstance(digest, str) or not _SHA.fullmatch(digest) or
                type(count) is not int or not 1 <= count <= _MAX_PAGES):
            raise ValueError("Missing or conflicting original PDF document identity")
        doc_hashes[ident] = digest
        expected.update((ident, p) for p in range(1, count + 1))
    page_map = {}
    for page in pages:
        key = (page.get("document_id"), page.get("page"))
        if key in page_map or key not in expected or page.get("coverage_status") not in (
                "EXAMINED", "UNRESOLVED", "BLOCKED"):
            raise ValueError("Duplicate, foreign or invalid sheet coverage disposition")
        page_map[key] = page
    if set(page_map) != expected:
        raise ValueError("Sheet count differs from original document page count")

    region_by_page = defaultdict(list)
    seen_ids = set()
    region_page_ids = {}
    for region in regions:
        key = (region.get("document_id"), region.get("page"))
        ident = region.get("region_id")
        if (key not in expected or not isinstance(ident, str) or ident in seen_ids
                or not ident.startswith(f"{key[0]}:p{key[1]}:")
                or region.get("status") not in ("EXAMINED", "UNRESOLVED", "BLOCKED")
                or region.get("physical_member_verified") is not False
                or region.get("financially_payable") is not False):
            raise ValueError("Unbound, duplicate or promoted PDF zone")
        seen_ids.add(ident)
        region_page_ids[ident] = key
        region_by_page[key].append(region)
    if (len(regions) != coverage.get("region_count") or
            any(len(region_by_page[k]) != page_map[k].get("region_count") for k in expected)):
        raise ValueError("Incomplete PDF source region crosswalk")

    unknown_by_page = defaultdict(list)
    seen_unknown = set()
    if len(unknown_visual) > len(regions):
        raise ValueError("Unbounded unknown visual coverage")
    for zone in unknown_visual:
        key = (zone.get("document_id"), zone.get("page"))
        ident = zone.get("region_id")
        if (key not in expected or region_page_ids.get(ident) != key
                or ident in seen_unknown
                or zone.get("status") != "UNRESOLVED_UNLABELED_VISUAL_REGION"
                or zone.get("financially_payable") is not False):
            raise ValueError("Unknown visual evidence is foreign, duplicated or promoted")
        seen_unknown.add(ident)
        unknown_by_page[key].append(ident)
    candidate_by_page = defaultdict(list)
    seen_candidates = set()
    for candidate in candidates:
        key = (candidate.get("document_id"), candidate.get("page"))
        ident = candidate.get("candidate_id")
        if (key not in expected or not isinstance(ident, str) or not ident or
                ident in seen_candidates or
                candidate.get("physical_member_verified") is not False or
                candidate.get("financially_payable") is not False):
            raise ValueError("Foreign, duplicate or approved detail candidate")
        candidate_regions = candidate.get("region_ids")
        candidate_families = candidate.get("family_candidates")
        if (not isinstance(candidate_regions, list) or not candidate_regions
                or any(region_page_ids.get(rid) != key for rid in candidate_regions)
                or not isinstance(candidate_families, list)):
            raise ValueError("Detail candidate has foreign region or malformed family provenance")
        seen_candidates.add(ident)
        candidate_by_page[key].append(candidate)

    rows = []
    for key in sorted(expected):
        document_id, page_number = key
        page = page_map[key]
        page_regions = region_by_page[key]
        blocked = (page["coverage_status"] == "BLOCKED" or
                   any(region["status"] == "BLOCKED" for region in page_regions))
        families = set()
        title_mark_ids = defaultdict(list)
        raw_families = page.get("discipline_candidates") or []
        if not isinstance(raw_families, list):
            raise ValueError("Unbounded sheet discipline metadata")
        for fam in raw_families:
            if fam in _FAMILIES:
                families.add(fam)
            else:
                # Keep even unknown, misspelled or unsupported classifications
                # in the unclassified row rather than silently dropping a trade.
                families.add("UNCLASSIFIED")
        for candidate in candidate_by_page[key]:
            for fam in candidate.get("family_candidates", []):
                family = fam if fam in _FAMILIES else "UNCLASSIFIED"
                families.add(family)
                title_mark_ids[family].append(candidate["candidate_id"])
        families.discard("UNCLASSIFIED")
        base = {
            "document_id": document_id, "page": page_number,
            "source_pdf_sha256": doc_hashes[document_id],
            "sheet_kind": page.get("sheet_kind"),
            "page_source_status": page["coverage_status"],
            "source_region_ids": sorted(r["region_id"] for r in page_regions),
            "blocked_region_ids": sorted(r["region_id"] for r in page_regions
                                          if r["status"] == "BLOCKED"),
            "unassigned_visual_region_ids": sorted(set(unknown_by_page[key])),
            "governing_revision_verified": False, "drawing_scale_verified": False,
            "level_scope_verified": False, "detail_boundary_verified": False,
            "physical_member_count": None, "quantity_approval_count": 0,
            "financially_payable": False,
        }
        for family in sorted(families):
            rows.append({
                **base,
                "coverage_id": f"{document_id}:p{page_number}:family:{family}",
                "candidate_family": family,
                "candidate_evidence_ids": sorted(set(title_mark_ids[family])),
                "status": ("BLOCKED_SOURCE_EVIDENCE_INCOMPLETE" if blocked
                           else "UNRESOLVED_CANDIDATE_FAMILY_NO_MEMBER_RECONCILIATION"),
                "required_review": [
                    "VERIFY_GOVERNING_SHEET_REVISION", "REVIEW_DETAIL_REGIONS_AND_SCALES",
                    "RECONCILE_PLAN_SECTION_DETAIL_LEVEL_AND_PHYSICAL_MEMBER"
                ],
            })
        # One mandatory remainder PER PAGE, regardless of family hints.
        # This prevents a named beam/column title from closing MEP/architecture.
        rows.append({
            **base,
            "coverage_id": f"{document_id}:p{page_number}:unclassified",
            "candidate_family": "UNCLASSIFIED_OR_OTHER_TRADES",
            "candidate_evidence_ids": [],
            "status": ("BLOCKED_SOURCE_EVIDENCE_INCOMPLETE" if blocked
                       else "UNRESOLVED_UNCLASSIFIED_SCOPE"),
            "required_review": [
                "CLASSIFY_ALL_REMAINING_VISUAL_AND_TEXT_REGIONS",
                "VERIFY_OTHER_STRUCTURAL_ARCHITECTURAL_MECHANICAL_ELECTRICAL_SCOPE",
                "REVIEW_DETAIL_BOUNDARIES_AND_GOVERNING_ISSUE",
            ],
        })
    if len({row["coverage_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate cross-discipline coverage identities")
    statuses = Counter(row["status"] for row in rows)
    return {
        "status": "BLOCKED_ENGINEERING_COVERAGE_PENDING",
        "page_count": len(expected), "family_candidate_rows": len(rows) - len(expected),
        "unclassified_page_count": len(expected),
        "coverage_rows": rows,
        "status_counts": dict(sorted(statuses.items())),
        "all_input_pages_accounted_for": True,
        "all_trades_reviewed": False, "all_details_interpreted": False,
        "physical_member_count": None, "quantity_approval_count": 0,
        "complete": False, "acceptance": "PARTIAL_NO_GO",
    }
