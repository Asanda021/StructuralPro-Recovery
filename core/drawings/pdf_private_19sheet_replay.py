"""Read-only private 19-sheet P8/P2-A PDF source/engine replay.

No source PDF or review crops are written into the repository or CI. The
preflight step may run without application modules, but MUST be identified as
INDEPENDENT_SOURCE_PREFLIGHT, not a successful application replay.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable

EXPECTED_PAGES = 19
_EXPECTED_HASH = re.compile(r"^[0-9a-f]{64}$")


def _json_input(path: str | None, expected_type: type):
    if path is None:
        return None
    source = Path(path)
    if source.stat().st_size > 128 * 1024:
        raise ValueError("Review witness exceeds 128 KiB")
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    if type(data) is not expected_type:
        raise ValueError("Review witness has wrong JSON root type")
    return data


def preflight_pdf(pdf_path: str | Path, expected_sha256: str) -> dict:
    """Read *every* source page with independent PyMuPDF, never infer a BOQ."""
    import pymupdf
    path = Path(pdf_path)
    if not _EXPECTED_HASH.fullmatch(expected_sha256):
        raise ValueError("A real, exact SHA-256 must be supplied")
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("Source must be a local PDF")
    digest_before = sha256(path.read_bytes()).hexdigest()
    if digest_before != expected_sha256:
        raise ValueError("Source PDF SHA-256 mismatch")
    rows = []
    with pymupdf.open(path) as doc:
        if len(doc) != EXPECTED_PAGES:
            raise ValueError(f"Expected {EXPECTED_PAGES} source pages, got {len(doc)}")
        for number, page in enumerate(doc, 1):
            if page.rect.width <= 0 or page.rect.height <= 0:
                raise ValueError("Invalid source page extent")
            try:
                words = len(page.get_text("words"))
                vectors = len(page.get_drawings())
            except (ValueError, RuntimeError) as exc:
                raise ValueError(f"Failed to parse source page {number}") from exc
            rows.append({"page": number, "native_words": words, "vector_drawings": vectors,
                         "page_width_pt": round(float(page.rect.width), 3),
                         "page_height_pt": round(float(page.rect.height), 3),
                         "rotation": page.rotation, "status": "SOURCE_READABLE_NOT_ENGINEERING_ACCEPTANCE"})
    if sha256(path.read_bytes()).hexdigest() != digest_before:
        raise ValueError("Source PDF changed during replay")
    return {"source_name": path.name, "sha256": digest_before, "page_count": len(rows),
            "source_status": "INDEPENDENT_SOURCE_PREFLIGHT_ONLY",
            "native_words": sum(x["native_words"] for x in rows),
            "vector_drawings": sum(x["vector_drawings"] for x in rows),
            "pages": rows, "accepted_member_count": 0, "quantity_approval_count": 0,
            "financially_payable": False}


def verify_engine_result(report: dict, preflight: dict, *, expected_beam_witnesses: int | None = None) -> dict:
    """Fail closed for incomplete, foreign, financial or inconsistent app results."""
    if not isinstance(report, dict) or not isinstance(report.get("documents"), list):
        raise ValueError("Invalid PDF engine output")
    docs = report["documents"]
    if (len(docs) != 1 or docs[0].get("sha256") != preflight["sha256"]
            or docs[0].get("page_count") != EXPECTED_PAGES
            or report.get("page_count") != EXPECTED_PAGES):
        raise ValueError("Engine document identity or page count mismatch")
    document_id = docs[0].get("document_id")
    if (not isinstance(document_id, str) or not document_id
            or docs[0].get("source_name") != preflight["source_name"]):
        raise ValueError("Engine source filename or document ID mismatch")
    graph = report.get("detail_evidence_graph")
    if (not isinstance(graph, dict) or len(graph.get("pages", [])) != EXPECTED_PAGES
            or not _EXPECTED_HASH.fullmatch(str(graph.get("graph_sha256", "")))
            or graph.get("acceptance") != "PARTIAL_NO_GO"
            or graph.get("complete") is not False
            or report.get("quantity_approval_count") != 0
            or graph.get("quantity_approval_count") != 0):
        raise ValueError("Incomplete or financially promoted engineering graph")
    observed_pages = [(row.get("document_id"), row.get("page")) for row in graph["pages"]]
    if set(observed_pages) != {(document_id, number) for number in range(1, EXPECTED_PAGES + 1)}:
        raise ValueError("Source page coverage contains gaps, duplicates or foreign sheets")
    for table in ("nodes", "edges", "issues"):
        if any(row.get("financially_payable") is not False for row in graph.get(table, ())):
            raise ValueError("Financially payable graph evidence is not allowed in PDF replay")
    for field in ("beam_profile_reviews", "beam_end_support_reviews", "occurrence_reviews"):
        for row in graph.get(field, ()):
            if (row.get("financially_payable") is not False
                    or row.get("physical_member_verified", False) is not False
                    or row.get("quantity_approved", False) is not False):
                raise ValueError("Unverified PDF member promoted to financial status")
    if expected_beam_witnesses is not None:
        if (len(graph.get("beam_profile_reviews", ())) != expected_beam_witnesses
                or len(graph.get("beam_end_support_reviews", ())) != expected_beam_witnesses):
            raise ValueError("Beam witness coverage absent or incomplete")
    return {"engine_status": "COMPLETE_READONLY_REPLAY_NONFINANCIAL", "graph_sha256": graph["graph_sha256"],
            "engine_page_count": EXPECTED_PAGES,
            "beam_profiles_reviewed": len(graph.get("beam_profile_reviews", ())),
            "beam_end_profiles_reviewed": len(graph.get("beam_end_support_reviews", ())),
            "beam_end_markers": sum(len(p.get("marker_candidates", ())) for p in graph.get("beam_end_marker_pages", ())),
            "structural_reviews": len(graph.get("structural_plan_reviews", ())),
            "fully_evidenced_member_count": graph.get("fully_evidenced_member_count"),
            "quantity_approval_count": 0,
            "financially_payable": False,
            "acceptance": "PARTIAL_NO_GO"}


def run_private_replay(pdf: str | Path, expected_sha: str, *, profile_json=None, axis_json=None,
                       detail_json=None, inspect: Callable | None = None) -> dict:
    preflight = preflight_pdf(pdf, expected_sha)
    if inspect is None:
        return {"source_preflight": preflight, "engine_status": "NOT_RUN_ENGINE_UNAVAILABLE",
                "acceptance": "PARTIAL_NO_GO", "quantity_approval_count": 0}
    if detail_json is not None and (profile_json is None or axis_json is None):
        raise ValueError("Detail witness requires beam profile and axis receipts")
    kwargs = {"max_documents": 1, "max_pages": EXPECTED_PAGES, "rendered_ocr": False}
    if profile_json is not None:
        kwargs["beam_profile_witnesses"] = _json_input(profile_json, list)
    if axis_json is not None:
        kwargs["beam_axis_labels"] = _json_input(axis_json, dict)
    if detail_json is not None:
        kwargs["beam_detail_profile_witnesses"] = _json_input(detail_json, list)
    result = inspect([str(pdf)], **kwargs)
    if sha256(Path(pdf).read_bytes()).hexdigest() != preflight["sha256"]:
        raise ValueError("PDF changed during full engine replay")
    strict = verify_engine_result(result, preflight,
                                  expected_beam_witnesses=len(kwargs["beam_profile_witnesses"])
                                  if "beam_axis_labels" in kwargs and "beam_profile_witnesses" in kwargs else None)
    return {"source_preflight": preflight, **strict}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private nonfinancial 19-sheet PDF replay")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--beam-profile-json")
    parser.add_argument("--axis-json")
    parser.add_argument("--detail-json")
    parser.add_argument("--engine", action="store_true", help="Import existing StructuralPro engine for full replay")
    args = parser.parse_args(argv)
    if args.engine:
        from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
        inspect = inspect_pdf_sheet_set
    else:
        inspect = None
    receipt = run_private_replay(args.pdf, args.expected_sha256, profile_json=args.beam_profile_json,
                                 axis_json=args.axis_json, detail_json=args.detail_json, inspect=inspect)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "PRIVATE_PDF_19SHEET_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "PRIVATE_PDF_19SHEET_PAGES.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = list(receipt["source_preflight"]["pages"][0])
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(receipt["source_preflight"]["pages"])
    print(json.dumps({k: v for k, v in receipt.items() if k != "source_preflight"}, ensure_ascii=False))


if __name__ == "__main__":
    main()