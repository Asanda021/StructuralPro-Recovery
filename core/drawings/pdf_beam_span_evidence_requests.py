"""Source-bound, nonfinancial missing-evidence register for PDF beam spans.

The register turns independently *reviewed* beam-plan/axis/detail observations
into precise document requests. It never certifies a member, support, profile,
level, fabrication length, scale or quantity, even when all visual marks agree.
No remote calls, data-base writes or source PDF exports are performed here.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")

_REQUESTS = (
    ("GOVERNING_DRAWING_ISSUE", "فهرست شیت‌ها و اصلاحیه ابلاغ‌شده با شماره، تاریخ و نسخه حاکم"),
    ("PHYSICAL_SUPPORT_IDENTITY", "نقشه یا جدول معتبر تعیین‌کننده نوع و هویت تکیه‌گاه واقعی در دو سر دهانه"),
    ("SPAN_SPECIFIC_CONNECTION_DETAIL", "شماره و شیت دیتیل اتصال قابل‌ارجاع برای همین دهانه، نه صرفاً پروفیل هم‌نام"),
    ("INSTALLATION_LEVEL", "تراز واقعی نصب و دامنه طبقات/تکرار این عضو در سند حاکم"),
    ("FABRICATION_CUT_LENGTH", "طول ساخت/برش تأییدشده با مبنای اندازه‌گیری و کسورات اتصال"),
    ("DIMENSION_UNIT_AND_CALIBRATION", "واحد معتبر و مرجع کالیبراسیون همین نما؛ نه فقط فاصله چاپی آکس"),
)
_GLYPH = ("PROFILE_VISUAL_GLYPH_CONFIRMATION", "خوانش مستقل و قطعی نوشته پروفیل روی نسخه حاکم نقشه")
_MARKER = ("BOTH_ENDPOINT_MARKERS_RECONCILIATION", "شناسایی و تأیید مستقل علامت دو سر دهانه در پلان")
_PROFILE_ONLY = ("TYPE_ONLY_DETAIL_IS_NOT_SPAN_REFERENCE", "تعیین ارجاع اختصاصی دهانه به دیتیل؛ هم‌نامی پروفیل کافی نیست")


def _bbox(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 4 or
            any(type(x) not in (int, float) or not isfinite(x) for x in value) or
            value[0] >= value[2] or value[1] >= value[3]):
        raise ValueError("Unbound or invalid source-local beam profile coordinates")
    return tuple(round(float(v), 4) for v in value)


def _identity(digest, page, bbox):
    return digest, page, _bbox(bbox)


def _key(*parts):
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "BEAM_MISSING_DOCUMENT:" + sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_beam_span_evidence_requests(graph, *, expected_sha256=None):
    """Return verified-source *requests*, not a member or payable takeoff.

    A missing/manual-free input is NOT_ASSESSED rather than a pass. Any source,
    identity, count or nonfinancial mismatch fails closed instead of generating
    plausible-looking designer requests for another drawing.
    """
    if not isinstance(graph, dict) or graph.get("acceptance") != "PARTIAL_NO_GO" or graph.get("complete") is not False:
        raise ValueError("PDF graph must remain partial and nonfinancial")
    # Unrelated reviewed occurrences may have nonfinancial temporary quantities.
    # Reject payment approval, but do not gate a PDF drawing's other families.
    if graph.get("quantity_approval_count") != 0:
        raise ValueError("Cannot generate an unresolved-beam receipt from approved quantities")
    if expected_sha256 is not None and (not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256)):
        raise ValueError("Expected source SHA-256 is invalid")

    profiles = graph.get("beam_profile_reviews", [])
    ends = graph.get("beam_end_support_reviews", [])
    if not isinstance(profiles, list) or not isinstance(ends, list):
        raise ValueError("Beam review graph tables must be lists")
    if not profiles and not ends:
        return {"status": "NOT_ASSESSED_MISSING_BEAM_WITNESSES", "requests": [],
                "summary": {"candidate_spans": 0, "source_identity_verified": False,
                            "open_document_request_count": 0, "verified_beam_members": 0,
                            "quantity_approval_count": 0, "financially_payable": False}}
    # Incremental review accepts profile-only receipts before axis labels.
    # Remain blocked: no physical span, end witness or payment is certified.
    if profiles and not ends:
        if len(profiles) > 256 or any(p.get("financially_payable") is not False
                                      for p in profiles if isinstance(p, dict)):
            raise ValueError("Unsafe or unbounded partial beam profile witnesses")
        return {"status": "BLOCKED_PENDING_INDEPENDENT_AXIS_AND_END_MARKERS", "requests": [],
                "summary": {"candidate_spans": len(profiles), "source_identity_verified": False,
                            "open_document_request_count": len(profiles), "verified_beam_members": 0,
                            "quantity_approval_count": 0, "financially_payable": False}}
    if not profiles or len(profiles) != len(ends) or len(profiles) > 256:
        raise ValueError("Incomplete visual beam profile / end-of-span correspondence")

    source_profiles = {}
    for profile in profiles:
        anchors = profile.get("anchors")
        if (not isinstance(anchors, list) or not anchors or not isinstance(anchors[0], dict)
                or profile.get("financially_payable") is not False or profile.get("physical_member_verified") is not False
                or profile.get("quantity_approved") is not False or profile.get("member_quantity") is not None):
            raise ValueError("Unsafe or unbound beam profile evidence")
        first = anchors[0]
        digest, page = first.get("source_sha256"), first.get("page")
        if not isinstance(digest, str) or not _SHA.fullmatch(digest) or type(page) is not int or page < 1:
            raise ValueError("Missing PDF profile source identity")
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("Foreign beam source SHA-256")
        ident = _identity(digest, page, first.get("bbox_pt"))
        if ident in source_profiles:
            raise ValueError("Duplicate beam profile source crop")
        source_profiles[ident] = profile

    result = []
    used = set()
    for end in ends:
        if (not isinstance(end, dict) or end.get("financially_payable") is not False
                or end.get("physical_member_verified") is not False
                or end.get("support_verified") is not False
                or end.get("detail_link_verified") is not False
                or end.get("member_quantity") is not None
                or end.get("verified_installed_length") is not None):
            raise ValueError("Nonfinancial span evidence was promoted without proof")
        digest, page = end.get("source_sha256"), end.get("beam_page")
        if not isinstance(digest, str) or not _SHA.fullmatch(digest) or type(page) is not int or page < 1:
            raise ValueError("Invalid beam-end source identity")
        ident = _identity(digest, page, end.get("plan_profile_bbox_pt"))
        profile = source_profiles.get(ident)
        if profile is None or ident in used:
            raise ValueError("Beam-end review has no unique corresponding profile crop")
        used.add(ident)
        if (end.get("profile_text") != profile.get("profile_text") or
                end.get("span_axes") != profile.get("span_axes") or
                end.get("printed_axis_row") != profile.get("printed_axis_row")):
            raise ValueError("Beam end/profile identity conflict")
        if (not isinstance(end.get("review_id"), str) or not end["review_id"] or
                not isinstance(end.get("status"), str) or
                not isinstance(end.get("detail_status"), str)):
            raise ValueError("Missing beam end review status")
        markers = end.get("endpoint_marker_ids")
        if not isinstance(markers, list) or len(markers) != 2:
            raise ValueError("Beam must have two explicit endpoint-marker slots")
        if any(x is not None and (not isinstance(x, str) or not x) for x in markers):
            raise ValueError("Invalid source-bound endpoint marker ID")
        if (type(end.get("candidate_detail_count")) is not int or end["candidate_detail_count"] < 0):
            raise ValueError("Invalid count of name-only connection details")

        needs = list(_REQUESTS)
        if profile.get("status") == "BLOCKED" or end["status"].startswith("BLOCKED_PROFILE_GLYPH"):
            needs.append(_GLYPH)
        if end["status"] != "PROPOSED_BOTH_END_GRID_SYMBOLS" or any(x is None for x in markers):
            needs.append(_MARKER)
        if end["candidate_detail_count"] > 0:
            needs.append(_PROFILE_ONLY)
        keys = [key for key, _ in needs]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate required evidence key")
        anchors = end.get("anchors") or []
        if not isinstance(anchors, list) or not anchors or any(
                a.get("source_sha256") != digest or type(a.get("page")) is not int or a["page"] < 1
                for a in anchors if isinstance(a, dict)) or any(not isinstance(a, dict) for a in anchors):
            raise ValueError("Foreign or missing document source anchors")
        result.append({
            "request_id": _key(digest, page, ident[2], end["review_id"]),
            "source_sha256": digest, "document_id": end.get("document_id"),
            "beam_page": page, "axis_page": end.get("axis_page"),
            "detail_page": end.get("detail_page"), "bbox_pt": list(ident[2]),
            "profile_review_id": profile.get("review_id"), "end_review_id": end["review_id"],
            "span_axes": end.get("span_axes"), "printed_axis_row": end.get("printed_axis_row"),
            "printed_mark": profile.get("circled_mark_raw"), "profile_visual": end["profile_text"],
            "end_marker_status": end["status"], "end_marker_ids": list(markers),
            "type_only_detail_status": end["detail_status"],
            "type_only_detail_matches": end["candidate_detail_count"],
            "status": "BLOCKED_REQUIRES_GOVERNING_ENGINEERING_DOCUMENTS",
            "required_evidence_codes": keys,
            "missing_evidence": keys,
            "required_evidence": [explanation for _, explanation in needs],
            "anchors": anchors,
            "span_specific_detail_verified": False, "installed_length_verified": False,
            "physical_member_verified": False, "member_quantity": None,
            "quantity_approved": False, "financially_payable": False,
        })

    if len(used) != len(source_profiles) or len({r["request_id"] for r in result}) != len(result):
        raise ValueError("Duplicate or missing span evidence request")
    result.sort(key=lambda r: (r["beam_page"], r["printed_axis_row"] or "",
                               r["span_axes"] or "", r["bbox_pt"]))
    counts = {code: sum(code in row["required_evidence_codes"] for row in result)
              for code, _ in [*_REQUESTS, _GLYPH, _MARKER, _PROFILE_ONLY]}
    return {"status": "BLOCKED_AWAITING_GOVERNING_ENGINEERING_DOCUMENTS",
            "requests": result,
            "summary": {"candidate_spans": len(result), "source_identity_verified": True,
                        "ambiguous_profile_glyphs": counts[_GLYPH[0]],
                        "two_end_symbols_proposed": sum(r["end_marker_status"] == "PROPOSED_BOTH_END_GRID_SYMBOLS" for r in result),
                        "name_only_detail_matches": sum(r["type_only_detail_matches"] > 0 for r in result),
                        "open_document_request_count": len(result),
                        "required_document_counts": counts,
                        "span_specific_detail_links": 0, "verified_beam_members": 0,
                        "quantity_approval_count": 0, "financially_payable": False}}


def write_beam_span_evidence_requests(register, directory):
    """Export privately: a reproducible JSON receipt and spreadsheet-friendly CSV.

    The operator decides where/if to share the request with the designer.
    """
    import csv
    from pathlib import Path
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "PRIVATE_BEAM_GOVERNING_DOCUMENT_REQUESTS.json").write_text(
        json.dumps(register, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    fields = ["request_id", "beam_page", "span_axes", "printed_axis_row", "printed_mark",
              "profile_visual", "end_marker_status", "type_only_detail_status",
              "required_evidence_codes", "status", "financially_payable"]
    with (folder / "PRIVATE_BEAM_GOVERNING_DOCUMENT_REQUESTS.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for request in register["requests"]:
            writer.writerow({key: ",".join(request[key]) if key == "required_evidence_codes" else request.get(key)
                             for key in fields})