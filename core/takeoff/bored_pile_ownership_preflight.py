"""Evidence-bound, read-only crosswalk for bored-pile ownership.

Stage-two prerequisite only. Never writes SQLite, changes a review state, or
issues any BOQ/payment authorization. Geometric ownership versus pile caps,
columns and historical entries requires an independent project-level gate.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

SCHEMA = "bored_pile_ownership_preflight_v1"
KINDS = frozenset(("concrete_net", "formwork", "rebar_longitudinal",
                   "rebar_spiral_ties", "rebar_crossties", "rebar_starters"))
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class OwnershipError(ValueError):
    """Fail-closed ownership evidence failure."""


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise OwnershipError(f"{label}: قرارداد فیلدها نامعتبر است")


def _id(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise OwnershipError(f"{label}: شناسه صریح معتبر لازم است")
    return value


def _canonical(value):
    text = unicodedata.normalize("NFKC", _id(value, "هویت"))
    return " ".join(text.replace("ي", "ی").replace("ك", "ک").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).casefold().split())


def _hash(value, label):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise OwnershipError(f"{label}: هش واقعی SHA-256 لازم است")
    return value


def read_evidence(path, expected_sha256):
    """Read checked bytes; a syntactically valid digest is not proof of authorship."""
    _hash(expected_sha256, "هش سند مالکیت")
    file = Path(path)
    if not file.is_file() or file.stat().st_size > 4 * 1024 * 1024:
        raise OwnershipError("فایل فیزیکی سند مالکیت لازم است")
    raw = file.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise OwnershipError("محتوای سند مالکیت تغییر کرده است")

    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise OwnershipError("کلید تکراری در سند مالکیت")
            result[k] = v
        return result

    def invalid_number(_):
        raise OwnershipError("عدد اعشاری JSON یا مقدار نامتناهی در سند مالکیت مجاز نیست")

    try:
        document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                              parse_float=invalid_number, parse_constant=invalid_number)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OwnershipError("JSON سند مالکیت قابل خواندن نیست") from exc
    if not isinstance(document, dict):
        raise OwnershipError("سند مالکیت باید شیء باشد")
    return document


def audit(data, compiled, evidence, *, existing_physical_claims=()):
    """Check documented row-to-owner claims without granting financial authority.

    existing_physical_claims is a complete caller-supplied set from another
    verified ledger; an incomplete set must never be interpreted as clearance.
    """
    _object(evidence, ("schema", "project_id", "floor_id", "group_id",
                       "input_sha256", "coordinate_ref", "prepared_by",
                       "reviewer", "allocations"), "سند مالکیت")
    if evidence["schema"] != SCHEMA:
        raise OwnershipError("نسخه قرارداد مالکیت نامعتبر است")
    for key in ("project_id", "floor_id", "group_id"):
        if _id(evidence[key], key) != _id(data[key], key):
            raise OwnershipError("هویت سند مالکیت با پروژه یا عضو مغایرت دارد")
    if _id(evidence["coordinate_ref"], "مختصات") != _id(data["datum"]["coordinate_ref"], "مختصات"):
        raise OwnershipError("مرجع مختصات سند مالکیت مغایرت دارد")
    if _hash(evidence["input_sha256"], "هش ورودی") != _hash(compiled["source_sha256"], "هش موتور"):
        raise OwnershipError("سند مالکیت به نسخه جاری ورودی متصل نیست")

    author = _canonical(evidence["prepared_by"])
    reviewer = _canonical(evidence["reviewer"])
    approved = {author}

    def collect(value):
        if isinstance(value, dict):
            if "approved_by" in value:
                approved.add(_canonical(value["approved_by"]))
            for v in value.values():
                collect(v)
        elif isinstance(value, list):
            for v in value:
                collect(v)

    collect(data)
    if reviewer in approved:
        raise OwnershipError("بازبین مستقل با تهیه‌کننده یا تأییدکننده دیتایل یکسان است")

    rows = compiled["rows"]
    if not isinstance(rows, list) or not rows:
        raise OwnershipError("خروجی واقعی موتور برای تطبیق لازم است")
    lookup = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") not in KINDS:
            raise OwnershipError("عملیات موتور ناشناخته است")
        key = (row["pile_id"], row["kind"], row["physical_id"])
        if key in lookup:
            raise OwnershipError("ردیف فیزیکی تکراری در موتور")
        lookup[key] = row

    series = {}
    piles = {}
    for pile in data["piles"]:
        piles[pile["id"]] = pile
        for kind, group in pile["rebars"].items():
            for bar in group.get("series", []):
                key = (pile["id"], "rebar_" + kind, bar["physical_id"])
                series[key] = bar

    allocations = evidence["allocations"]
    if not isinstance(allocations, list) or not allocations:
        raise OwnershipError("تخصیص‌های صریح لازم است")
    selected = set()
    claim_keys = set()
    claimed_rows = []
    excluded = []
    for item in allocations:
        _object(item, ("pile_id", "operation", "physical_id", "scope_id",
                       "payer_kind", "payer_id", "bar_piece_ids",
                       "evidence_ref", "evidence_sha256"), "تخصیص")
        key = (_id(item["pile_id"], "شمع"), _id(item["operation"], "عملیات"),
               _id(item["physical_id"], "قطعه"))
        if key not in lookup or key in selected:
            raise OwnershipError("تخصیص فاقد ردیف موتور یا تکراری است")
        selected.add(key)
        scope = _canonical(item["scope_id"])
        _id(item["evidence_ref"], "مرجع مدرک تخصیص")
        _hash(item["evidence_sha256"], "هش مدرک تخصیص")
        payer_kind = item["payer_kind"]
        if payer_kind not in ("pile", "other_member"):
            raise OwnershipError("مالک پرداخت باید صریح باشد")
        payer = _canonical(item["payer_id"])
        own_pile = _canonical(piles[key[0]]["physical_id"])
        if (payer_kind == "pile") != (payer == own_pile):
            raise OwnershipError("هویت مالک پرداخت با شمع یا عضو دیگر مغایرت دارد")
        pieces = item["bar_piece_ids"]
        if not isinstance(pieces, list):
            raise OwnershipError("هویت فردی میلگردها لازم است")
        if key[1].startswith("rebar_"):
            bar = series.get(key)
            if bar is None or isinstance(bar["count"], (float, bool)):
                raise OwnershipError("سری میلگرد معتبر نیست")
            count = int(bar["count"])
            if str(count) != str(bar["count"]) or count <= 0 or len(pieces) != count:
                raise OwnershipError("تعداد هویت فردی با سری میلگرد برابر نیست")
            claims = [("bar", _canonical(piece)) for piece in pieces]
            claims += [("bar_series", _canonical(key[2]))]
        else:
            if pieces:
                raise OwnershipError("هویت میلگرد برای عملیات بتن/قالب مجاز نیست")
            claims = [("formwork" if key[1] == "formwork" else "concrete", scope)]
        for claim in claims:
            if claim in claim_keys:
                raise OwnershipError("مالکیت فیزیکی یا میلگرد در دو عملیات تکرار شده است")
            claim_keys.add(claim)
        if payer_kind == "pile":
            claimed_rows.append(deepcopy(lookup[key]))
        else:
            excluded.append({"pile_id": key[0], "operation": key[1],
                             "physical_id": key[2], "reason": "مالک پرداخت عضو دیگر است"})

    for key, row in lookup.items():
        if key not in selected:
            excluded.append({"pile_id": key[0], "operation": key[1],
                             "physical_id": key[2], "reason": "مالکیت تخصیص نیافته است"})

    old_claims = set()
    for category, physical in existing_physical_claims:
        old_claims.add((category, _canonical(physical)))
    if claim_keys & old_claims:
        raise OwnershipError("ادعای فیزیکی با دفتر مالکیت قبلی تکراری است")

    blockers = ["مالکیت مشترک با کلاهک، ستون و اعضای تاریخی نیازمند تطبیق مستقل Snapshot و هندسه است",
                "هش مدرک به‌تنهایی اصالت نقشه، مالکیت یا اختیار امضا را اثبات نمی‌کند"]
    if any(pile["interface"]["ownership_status"] == "review_required" for pile in data["piles"]):
        blockers.append("وضعیت اتصال یک یا چند شمع هنوز نیازمند بررسی است")
    return {"schema": SCHEMA, "status": "READ_ONLY_PENDING_CROSS_MEMBER_GATE",
            "commit_allowed": False, "ready_for_boq": False,
            "candidate_owned_rows": claimed_rows, "excluded_operations": excluded,
            "physical_claims": sorted([list(c) for c in claim_keys]),
            "blockers": blockers}
