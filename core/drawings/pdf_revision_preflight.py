"""Build an unapproved PDF revision register template and source review ledger.

Hash identity is known from the PDF bytes; current/superseded status, issued
revision, project, issue, and authority MUST be supplied independently.
No acceptance, BOQ or project writes happen in this module.
"""
from __future__ import annotations

from collections import defaultdict
from re import fullmatch
from typing import Mapping


def build_pdf_revision_register_draft(report: Mapping) -> dict:
    """Return JSON schema-v1 template with deliberately null authority fields."""
    if not isinstance(report, Mapping):
        raise ValueError("PDF draft requires an intake report")
    docs = report.get("documents")
    if not isinstance(docs, (list, tuple)) or not 1 <= len(docs) <= 100:
        raise ValueError("PDF draft requires bounded sources")
    seen_ids, seen_hashes, sources = set(), set(), []
    for doc in docs:
        if not isinstance(doc, Mapping):
            raise ValueError("Invalid PDF document entry")
        did, digest, count = doc.get("document_id"), doc.get("sha256"), doc.get("page_count")
        if (not isinstance(did, str) or not did or did in seen_ids or
                not isinstance(digest, str) or not fullmatch("[0-9a-f]{64}", digest) or
                digest in seen_hashes or type(count) is not int or count < 1):
            raise ValueError("Invalid or duplicate PDF source identity")
        seen_ids.add(did)
        seen_hashes.add(digest)
        sources.append((did, digest, count, str(doc.get("source_name") or did)[:250]))
    if sum(item[2] for item in sources) > 500:
        raise ValueError("PDF draft page budget exceeded")

    graph = report.get("detail_evidence_graph") or {}
    if not isinstance(graph, Mapping):
        raise ValueError("Invalid PDF evidence graph")
    raw_pages = graph.get("pages", ())
    if not isinstance(raw_pages, (list, tuple)):
        raise ValueError("Invalid PDF page evidence")
    by_page = {}
    for entry in raw_pages:
        if not isinstance(entry, Mapping):
            raise ValueError("Invalid PDF page evidence entry")
        key = entry.get("document_id"), entry.get("page")
        if key in by_page or key[0] not in seen_ids or type(key[1]) is not int or key[1] < 1:
            raise ValueError("Duplicate or foreign PDF page evidence")
        revisions = entry.get("printed_revisions") or ()
        if not isinstance(revisions, (list, tuple)) or any(
                not isinstance(rev, str) or not rev for rev in revisions):
            raise ValueError("Invalid printed PDF revision evidence")
        by_page[key] = sorted(set(revisions))
    if raw_pages:
        expected = {(did, n) for did, _, count, _ in sources
                    for n in range(1, count + 1)}
        if set(by_page) != expected:
            raise ValueError("Incomplete PDF page inventory for draft")

    template, audit = [], []
    for did, digest, count, name in sorted(sources):
        revisions = sorted({rev for n in range(1, count+1)
                            for rev in by_page.get((did, n), ())})
        unread = [n for n in range(1, count+1) if not by_page.get((did, n))]
        conflicting = [n for n in range(1, count+1)
                       if len(by_page.get((did, n), ())) > 1]
        warnings = ["GOVERNING_ISSUE_AUTHORITY_REQUIRED"]
        if not raw_pages:
            warnings.append("PAGE_EVIDENCE_NOT_ATTACHED")
        if unread:
            warnings.append("PRINTED_REVISION_NOT_VERIFIED_ON_ALL_PAGES")
        if len(revisions) > 1:
            warnings.append("MULTI_REVISION_PDF_REQUIRES_PAGE_SPECIFIC_AUTHORITY")
        if conflicting:
            warnings.append("CONFLICTING_PRINTED_REVISIONS_ON_PAGE")
        template.append({
            "sha256": digest, "project_id": None, "issue_id": None,
            "revision": None, "status": None, "authority_reference": None,
        })
        audit.append({
            "document_id": did, "source_name": name, "sha256": digest,
            "page_count": count, "printed_revision_candidates": revisions,
            "pages_without_printed_revision": unread,
            "pages_with_conflicting_revisions": conflicting,
            "required_actions": warnings, "financially_payable": False,
        })
    return {
        "template": {"schema_version": 1, "documents": template},
        "review": audit,
        "source_document_count": len(sources),
        "source_page_count": sum(entry[2] for entry in sources),
        "requires_official_issue_register": True,
        "valid_register_to_attach": False,
        "quantity_approval_count": 0, "financially_payable": False,
        "complete": False, "acceptance": "PARTIAL_NO_GO",
    }
