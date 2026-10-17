"""Read-only, additive preparation bridge for the reviewed RC shear-wall engine.

NEVER writes ProjectStore/SQLite, reuses legacy BOQ/Takeoff semantics, and does
not authorize commitment. AEC registration, review, financial/physical ownership
and amendments must still be integrated and tested by the controlling workflow.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from core.takeoff.shear_wall_specialist_chat import preview as engine_preview, ident
from core.takeoff.commit_guards import require_source_unused, validate_commit_rows

BRIDGE_POLICY = "shear_wall_aec_bridge_chat_v1"
PAYABLE_KINDS = {"concrete_net", "formwork_main", "formwork_edge"}
REBAR_GROUPS = (
    "vertical", "horizontal", "boundary_longitudinal", "boundary_ties",
    "crossties", "opening_reinforcement", "starters_connections",
)
CODES = {
    "concrete_net": "shear_wall_concrete",
    "formwork_main": "shear_wall_formwork_main",
    "formwork_edge": "shear_wall_formwork_edge",
    **{"rebar_" + group: "shear_wall_rebar_" + group for group in REBAR_GROUPS},
}
_LABELS = {
    "concrete_net": "بتن خالص دیوار برشی مستند",
    "formwork_main": "قالب وجه اصلی دیوار برشی مستند",
    "formwork_edge": "قالب وجه جانبی دیوار برشی مستند",
    **{"rebar_" + group: "آرماتور دیوار برشی ـ " + group for group in REBAR_GROUPS},
}


class ShearBridgeError(ValueError):
    """Conservative stage-only error, never replaced by an automatic fallback."""


def _record_project(project: dict, data: dict) -> None:
    if not isinstance(project, dict) or not isinstance(project.get("id"), str):
        raise ShearBridgeError("شناسه پروژه مرجع و Snapshot لازم است")
    if ident(project["id"], label="شناسه پروژه") != ident(data["project_id"], label="شناسه پروژه موتور"):
        raise ShearBridgeError("شناسه پروژه و محاسبه دیوار برشی یکسان نیست")
    for name in ("reviewed_aec_systems", "reviewed_structural_members", "beam_detail_register"):
        registry = project.get(name) or {}
        if not isinstance(registry, dict):
            raise ShearBridgeError("دفتر ثبت پروژه ناسازگار است")
        for value in registry.values():
            if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
                raise ShearBridgeError("رکورد ثبت‌شده ساختار معتبر ندارد")
            previous = value["data"]
            if previous.get("kind") != "shear_wall":
                continue
            if ident(previous.get("floor_id"), label="طبقه موجود") != ident(data["floor_id"], label="طبقه جاری"):
                continue
            if ident(previous.get("system_id") or previous.get("member_id") or "", label="شناسه موجود") == ident(data["wall_id"], label="دیوار جدید"):
                raise ShearBridgeError("دیوار قبلاً در مسیر عمومی یا تخصصی AEC ثبت شده است؛ مهاجرت خاموش ممنوع")
            g = previous.get("geometry") or previous.get("architecture_detail", {}).get("geometry", {})
            if isinstance(g, dict) and g.get("physical_wall_id") and ident(g["physical_wall_id"], label="هویت موجود") == ident(data["physical_wall_id"], label="هویت جدید"):
                raise ShearBridgeError("هویت فیزیکی دیوار قبلاً به رکورد دیگری تخصیص یافته است")
    require_source_unused(project, data["source"]["source_id"])
    for row in project.get("takeoffs") or []:
        if not isinstance(row, dict) or not isinstance(row.get("params") or {}, dict):
            raise ShearBridgeError("ریزمتره ذخیره‌شده فاقد ساختار معتبر است")
        params = row.get("params") or {}
        if params.get("physical_wall_id") and ident(params["physical_wall_id"], label="دیوار قبلی") == ident(data["physical_wall_id"], label="دیوار جدید"):
            raise ShearBridgeError("دیوار قبلاً در برداشت ثبت شده است")


def _review_evidence(data: dict, independent_reviewer: str | None, review_reference: str | None) -> dict:
    if not independent_reviewer or not isinstance(independent_reviewer, str) or not independent_reviewer.strip():
        raise ShearBridgeError("بازبین مستقل لازم است")
    if not review_reference or not isinstance(review_reference, str) or not review_reference.strip():
        raise ShearBridgeError("مدرک مستقل کنترل مالکیت حجم و میلگرد لازم است")
    reviewer = ident(independent_reviewer, label="بازبین")
    # Review independence covers nested drawing contacts, bar cut details and
    # formwork edge scope too. Missing approval fields are checked by engine.
    approved = []
    def collect(value):
        if isinstance(value, dict):
            if "approved_by" in value:
                approved.append(value["approved_by"])
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
    collect(data)
    approved.append(data["formwork"]["payment_approved_by"])
    if reviewer in {ident(x, label="تأییدکننده") for x in approved}:
        raise ShearBridgeError("بازبین مستقل نباید تأییدکننده همان دیتایل باشد")
    return {"reviewer": independent_reviewer.strip(), "reference": review_reference.strip()}


def compile_preview(data: dict, project: dict, *, reviewer: str | None = None,
                    review_reference: str | None = None) -> dict:
    """Build exact, *uncommitted* AEC-style and takeoff candidate rows.

    The result is intentionally NOT ready for commit: no cross-member geometry
    can be trusted without an independently signed ownership reconciliation,
    current store CAS, amendment and financial lock checks by the existing flow.
    """
    if not isinstance(data, dict):
        raise ShearBridgeError("داده موتور معتبر نیست")
    calculated = engine_preview(data)
    _record_project(project, data)
    evidence = _review_evidence(data, reviewer, review_reference)

    wall, floor = data["wall_id"], data["floor_id"]
    prefix = f"aec:shear_wall:{floor}:{wall}"
    gross = {r["segment_id"]: r for r in calculated["rows"] if r["kind"] == "concrete_gross"}
    deductions = {}
    for r in calculated["rows"]:
        if r["kind"] in ("concrete_opening_deduction", "concrete_interface_deduction"):
            deductions.setdefault(r["segment_id"], []).append(r)
    prepared = []
    takeoffs = []
    checked_rows = []
    for entry in calculated["rows"]:
        kind = entry["kind"]
        if kind not in CODES:  # Exclude gross amounts and NEGATIVE rows from payable BOQ
            continue
        quantity = Decimal(entry["quantity"])
        if quantity < 0:
            raise ShearBridgeError("پرداخت منفی در قرارداد پل مجاز نیست")
        if quantity == 0:
            continue  # Zero/Not-required face is documented, not a payable row
        physical = ident(entry["physical_id"], label="شناسه ردیف")
        source_id = f"{prefix}:{kind}:{physical}"
        if source_id in checked_rows:
            raise ShearBridgeError("ردیف مالی دارای هویت تکراری است")
        checked_rows.append(source_id)
        component = "concrete" if kind == "concrete_net" else ("formwork" if kind.startswith("formwork") else kind)
        params = {
            "bridge_policy": BRIDGE_POLICY,
            "source_input_sha256": calculated["input_sha256"],
            "physical_wall_id": data["physical_wall_id"],
            "physical_claims": calculated["physical_claims"],
            "physical_component_id": entry["physical_id"],
            "physical_kind": kind,
            "source_refs": list(entry["source_refs"]),
            "axis_ref": data["datum"]["axis_ref"],
            "coordinate_ref": data["datum"]["coordinate_ref"],
            "level_ref": data["datum"]["level_ref"],
        }
        if kind == "concrete_net":
            part = entry["segment_id"]
            params["gross_concrete_m3"] = gross[part]["quantity"]
            # The native commit guard can reject reuse of these documented
            # deduction IDs, but ONLY a separately reviewed owner ledger can
            # verify whether the foreign member previously claimed the volume.
            params["intersections"] = [
                {"id": f"shear:{floor}:{wall}:{d['kind']}:{d['physical_id']}",
                 "source_ref": d["source_refs"][0],
                 "volume_m3": str(-Decimal(d["quantity"]))}
                for d in deductions.get(part, [])
            ]
        row = {
            "source_id": source_id, "line_id": physical,
            "item_code": CODES[kind], "quantity": str(quantity), "unit": entry["unit"],
            "domain": "building", "description": _LABELS[kind] + " " + wall,
            "formula": entry["formula"], "params": params,
            "component": component, "method": BRIDGE_POLICY,
            "source_ref": entry["source_refs"][0], "role": "work",
        }
        prepared.append(row)
        takeoffs.append({
            "id": source_id, "member_code": wall, "source_id": source_id,
            "domain": "building", "item": row["item_code"], "system": floor,
            "description": row["description"], "params": deepcopy(params),
            "provenance": deepcopy(data["source"]),
            "review": {"approved_by": evidence["reviewer"], "component": component,
                       "method": BRIDGE_POLICY, "measurement_source": row["source_ref"],
                       "review_reference": evidence["reference"]},
            "quantities": [{"code": row["item_code"], "title": row["description"],
                            "system": floor, "unit": row["unit"],
                            "amount": row["quantity"], "formula": row["formula"],
                            "role": "work", "price_code": None, "unit_price": None}],
        })

    summed = {
        "concrete_net": sum((Decimal(x["quantity"]) for x in prepared if x["item_code"] == CODES["concrete_net"]), Decimal(0)),
        "formwork": sum((Decimal(x["quantity"]) for x in prepared if x["item_code"] in (CODES["formwork_main"], CODES["formwork_edge"])), Decimal(0)),
        "rebar": sum((Decimal(x["quantity"]) for x in prepared if x["item_code"].startswith("shear_wall_rebar_")), Decimal(0)),
    }
    expected = calculated["totals"]
    if (summed["concrete_net"] != Decimal(expected["net_concrete_m3"]) or
        summed["formwork"] != Decimal(expected["payable_formwork_m2"]) or
        summed["rebar"] != Decimal(expected["rebar_kg"])):
        raise ShearBridgeError("حاصل ردیف‌های پل با خروجی مستقل موتور یکسان نیست")
    # Existing commit guards must accept the shape, but we NEVER persist.
    validate_commit_rows(project, takeoffs, source_id=data["source"]["source_id"])
    return {
        "policy": BRIDGE_POLICY,
        "status": "preview_only_not_integrated",
        "commit_allowed": False,
        "blockers": [
            "نیازمند مالکیت مستقل بتن/میلگرد در برابر ستون، تیر و فونداسیون و تأیید کسورات مشترک",
            "نیازمند اتصال نسخه‌دار به AEC، بازبینی، CAS، اصلاحیه، BOQ و گزارش‌های مشترک",
        ],
        "source_sha256": calculated["input_sha256"],
        "identity": deepcopy(calculated["identity"]),
        "totals": deepcopy(calculated["totals"]),
        "preview_rows": prepared,
        "takeoff_candidates": takeoffs,
        "excluded_nonpayable_kinds": sorted(set(r["kind"] for r in calculated["rows"]) - set(CODES)),
        "review_reference": evidence["reference"],
    }
