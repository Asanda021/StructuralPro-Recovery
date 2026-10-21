"""Read-only AEC/BOQ preparation bridge for the independently sourced stair engine.

This module must NEVER commit to ProjectStore/SQLite. It produces immutable-format
candidate rows checked against the existing source/BOQ guards, but independent
structural volume and bar ownership, CAS, amendment, and financial checks remain
unresolved until the controlling Work integration. No other engines are changed.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext, Inexact, Rounded

from core.takeoff.stair_specialist import preview as stair_preview, StairValidationError
from core.takeoff.commit_guards import (
    require_source_unused, validate_commit_rows, rebuild_project_boq,
)

POLICY = "stair_bridge_chat_preflight_v1"
CONCRETE_OPS = ("waist_concrete", "step_concrete", "landing_concrete")
OPERATIONS = {
    **{k: ("stair_" + k, "m3", "بتن " + {
        "waist_concrete": "شمشیری", "step_concrete": "کف‌پله", "landing_concrete": "پاگرد",
    }[k]) for k in CONCRETE_OPS},
    "formwork": ("stair_formwork", "m2", "قالب‌بندی پله"),
    **{("rebar_" + k): ("stair_rebar_" + k, "kg", "آرماتور پله ـ " + k)
       for k in ("flight_main", "flight_distribution", "flight_top_extra",
                 "flight_bottom_extra", "landing", "starter", "connection", "special")},
}


class StairBridgeError(ValueError):
    """Fail-closed preparation error; no implicit migration or owner inference."""


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise StairBridgeError(f"{label}: شناسه یا مدرک صریح غیرخالی بدون فاصله اضافی لازم است")
    return value


def _approved_actors(node):
    if isinstance(node, dict):
        for key in ("approved_by", "reviewed_by"):
            if key in node and isinstance(node[key], str) and node[key].strip():
                yield node[key].strip().casefold()
        for value in node.values():
            yield from _approved_actors(value)
    elif isinstance(node, list):
        for value in node:
            yield from _approved_actors(value)


def _registered_collision(project, data, source_id):
    if not isinstance(project, dict):
        raise StairBridgeError("تصویر پروژه باید شیء معتبر باشد")
    if _text(project.get("id"), "شناسه پروژه") != data["metadata"]["project_id"]:
        raise StairBridgeError("شناسه پروژه موتور با تصویر پروژه سازگار نیست")
    floor, stair_id = data["metadata"]["floor_id"], data["metadata"]["stair_id"]
    for register in ("reviewed_aec_systems", "reviewed_structural_members", "beam_detail_register"):
        records = project.get(register) or {}
        if not isinstance(records, dict):
            raise StairBridgeError("دفتر ثبت قبلی ساختار نامعتبر دارد")
        for rec in records.values():
            if not isinstance(rec, dict) or not isinstance(rec.get("data"), dict):
                raise StairBridgeError("رکورد قبلی ناقص است")
            old = rec["data"]
            if old.get("kind") != "stair" or old.get("floor_id") != floor:
                continue
            if (old.get("system_id") == stair_id or old.get("member_id") == stair_id
                    or old.get("stair_id") == stair_id
                    or (old.get("geometry") or {}).get("physical_stair_id") == stair_id):
                raise StairBridgeError("پله با هویت قبلی در دفتر متره وجود دارد؛ مهاجرت خاموش مجاز نیست")
    for row in project.get("takeoffs") or []:
        if not isinstance(row, dict) or not isinstance(row.get("params") or {}, dict):
            raise StairBridgeError("ردیف ثبت‌شده قبلی نامعتبر است")
        params = row.get("params") or {}
        if (params.get("physical_stair_id") == stair_id and params.get("floor_id") == floor):
            raise StairBridgeError("هویت فیزیکی پله قبلاً ثبت شده است")
        if row.get("member_code") == stair_id and row.get("system") == floor and (
            row.get("item") == "stair" or str(row.get("item", "")).startswith("stair_")
        ):
            raise StairBridgeError("پله قبلاً از مسیر تاریخی ثبت شده است")
    require_source_unused(project, source_id)


def compile_preview(data: dict, project: dict, *, source_id: str,
                    reviewer: str, ownership_reference: str) -> dict:
    """Return source-bound exact candidate takeoffs; no right to commit is granted.

    `ownership_reference` is only a *claim of supporting documentation*. This
    bridge does not independently adjudicate shared concrete/bar ownership.
    """
    source_id = _text(source_id, "شناسه برداشت")
    reviewer = _text(reviewer, "بازبین مستقل")
    ownership_reference = _text(ownership_reference, "مرجع بررسی مالکیت مشترک")
    if not isinstance(data, dict):
        raise StairBridgeError("داده موتور معتبر نیست")
    # Keep the authoritative engineering engine intact and fail closed.
    calculated = stair_preview(data)
    if calculated.get("ready_for_boq") is not False:
        raise StairBridgeError("قرارداد پیش‌نمایش مستقل تغییر کرده؛ بازبینی لازم است")
    metadata = data["metadata"]
    if reviewer.casefold() in set(_approved_actors(data)):
        raise StairBridgeError("بازبین مستقل نباید همان تأییدکننده ورودی، شکل یا قالب باشد")
    _registered_collision(project, data, source_id)
    project = deepcopy(project)  # Do not mutate the caller even in preview.

    seen_row_ids = set()
    seen_physical_operations = set()
    candidate_rows = []
    quantities = {"waist_concrete": [], "step_concrete": [],
                  "landing_concrete": [], "formwork": [], "reinforcement": []}
    for entry in calculated["rows"]:
        if not isinstance(entry, dict) or entry.get("operation") not in OPERATIONS:
            raise StairBridgeError("عملیات ناشناخته یا ردیف کسر غیرقابل پرداخت")
        op = entry["operation"]
        code, unit, label = OPERATIONS[op]
        if entry.get("unit") != unit:
            raise StairBridgeError("واحد خروجی موتور پله با قرارداد مالی مغایر است")
        quantity = Decimal(entry["quantity_exact"])
        if not quantity.is_finite() or quantity <= 0:
            raise StairBridgeError("مقدار مثبت و متناهی برای ردیف کاری لازم است")
        physical = _text(entry.get("physical_id"), "شناسه فیزیکی")
        operation_id = (op, physical)
        if operation_id in seen_physical_operations:
            raise StairBridgeError("محاسبه تکراری یک عملیات روی قطعه فیزیکی")
        seen_physical_operations.add(operation_id)
        sid = ("aec:stair:" + metadata["floor_id"] + ":" + metadata["stair_id"] + ":"
               + entry["source_id"])
        if sid in seen_row_ids:
            raise StairBridgeError("هویت ردیف کاری تکراری است")
        seen_row_ids.add(sid)
        label = label + " مستند — " + metadata["stair_id"]
        params = {
            "stair_bridge_policy": POLICY,
            "source_input_sha256": calculated["input_sha256"],
            "physical_stair_id": metadata["stair_id"], "floor_id": metadata["floor_id"],
            "physical_component_id": physical, "physical_operation": op,
            "source_reference": _text(entry.get("source_ref"), "مدرک ردیف"),
            "stair_input_source_id": source_id,
            "review_reference": ownership_reference,
        }
        candidate_rows.append({
            "id": sid, "source_id": sid, "member_code": metadata["stair_id"],
            "domain": "building", "item": code, "system": metadata["floor_id"],
            "description": label, "params": params,
            "provenance": {"source_id": source_id, "source_ref": metadata["source_ref"],
                           "input_sha256": calculated["input_sha256"]},
            "review": {"approved_by": reviewer, "method": POLICY,
                       "measurement_source": entry["source_ref"],
                       "ownership_reference": ownership_reference},
            "quantities": [{"code": code, "title": label, "unit": unit,
                            "amount": str(quantity), "formula": entry["formula"],
                            "role": "work", "price_code": None, "unit_price": None}],
        })
        key = "reinforcement" if op.startswith("rebar_") else op
        quantities[key].append(quantity)

    if not candidate_rows:
        raise StairBridgeError("ردیف متره مستقلی برای پله وجود ندارد")
    # Decimal's default 28-digit context must NOT silently round aggregated
    # quantities derived from the 65-digit specialist engine.
    with localcontext() as context:
        context.prec = max(512, sum(len(q.as_tuple().digits) for values in quantities.values() for q in values) + 16)
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        totals = {key: str(sum(values, Decimal(0))) for key, values in quantities.items()}
    validate_commit_rows(project, candidate_rows, source_id=source_id)
    # A dry-run of existing commercial aggregation is NOT a commit/financial approval.
    _, boq = rebuild_project_boq(project, list(project.get("takeoffs") or []) + candidate_rows)
    return {
        "policy": POLICY,
        "status": "preview_only_not_integrated",
        "commit_allowed": False,
        "source_sha256": calculated["input_sha256"],
        "source_id": source_id,
        "identity": {"project_id": metadata["project_id"],
                     "floor_id": metadata["floor_id"], "stair_id": metadata["stair_id"]},
        "totals_exact": totals,
        "takeoff_candidates": candidate_rows,
        "boq_dry_run": boq,
        "blockers": [
            "تعیین مالکیت مستقل حجم بتن و میلگرد پله نسبت به تیر/ستون/دال/پاگرد و مرجع مالی",
            "اتصال به فرم فارسی، گردش نسخه‌دار SQLite/CAS، بازبینی و اصلاحیه و گزارش‌های مشترک",
            "مدرک موجود به‌تنهایی جایگزین تأیید فنی و تطبیق هندسه سه‌بعدی اعضا نیست",
        ],
        "engine_ready_for_boq": False,
    }
