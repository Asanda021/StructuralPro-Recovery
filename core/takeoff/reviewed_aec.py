"""AEC reviewed system contracts for structural details, roofing, finishes and MEP.

Separate auditable physical components; unknown components are not treated as zero.
All calculation is delegated to the existing TakeoffEngine or explicitly approved
measured quantities. No automatic pricebook, dimensions, waste or reinforcement.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from typing import Any

from core.takeoff.boq import build_boq
from core.takeoff.engine import TakeoffEngine
from core.takeoff.units import normalize_unit
from core.takeoff.reviewed_components import require_text, positive
from core.takeoff.reviewed_structural import _validate_source

REGISTER = "reviewed_aec_systems"


@dataclass(frozen=True)
class SystemSpec:
    title: str
    components: tuple[str, ...]
    essential: tuple[str, ...]


SPECS = {
    # Priority 6: structural concrete other than columns, beams and footings.
    "shear_wall": SystemSpec("دیوار برشی", ("concrete", "vertical_rebar", "horizontal_rebar",
                                             "boundary_rebar", "crossties", "formwork",
                                             "openings"), ("concrete", "vertical_rebar", "horizontal_rebar")),
    "stair": SystemSpec("پله", ("waist_concrete", "step_concrete", "landing_concrete",
                                "reinforcement", "formwork", "finishes"), ("waist_concrete",)),
    # Priority 7: concrete and steel/composite roof families as distinct assemblies.
    "solid_slab": SystemSpec("دال بتنی", ("concrete", "top_rebar", "bottom_rebar",
                                          "edge_beams", "formwork", "openings"), ("concrete",)),
    "joist_block": SystemSpec("سقف تیرچه‌بلوک", ("topping", "ribs", "joists", "blocks",
                                               "ties", "reinforcement", "formwork",
                                               "openings"), ("topping", "ribs", "joists", "blocks")),
    "joist_foam": SystemSpec("سقف تیرچه‌یونولیت", ("topping", "ribs", "joists", "foam",
                                                "ties", "reinforcement", "formwork",
                                                "openings"), ("topping", "ribs", "joists", "foam")),
    "waffle": SystemSpec("سقف وافل", ("topping", "ribs_x", "ribs_y", "junction_adjustment",
                                    "solid_zones", "reinforcement", "forms", "openings"),
                         ("topping", "ribs_x", "ribs_y", "junction_adjustment")),
    "uboot": SystemSpec("سقف یوبوت", ("gross_concrete", "verified_voids", "solid_zones",
                                    "reinforcement", "formwork", "openings"),
                         ("gross_concrete", "verified_voids")),
    "cobiax": SystemSpec("سقف کوبیاکس", ("gross_concrete", "verified_voids", "solid_zones",
                                      "reinforcement", "formwork", "openings"),
                          ("gross_concrete", "verified_voids")),
    "hollow_core": SystemSpec("سقف هالوکور", ("precast_panels", "joints", "topping",
                                           "reinforcement", "bearings", "openings"),
                              ("precast_panels",)),
    "steel_deck": SystemSpec("سقف عرشه فولادی", ("deck_sheet", "deck_concrete", "studs",
                                                "mesh", "edge_plates", "openings"),
                             ("deck_sheet", "deck_concrete")),
    # Priority 8: material-by-material architecture and independent services.
    "block_wall": SystemSpec("دیوار بلوکی", ("blocks", "mortar", "reinforcement",
                                           "lintels", "openings"), ("blocks", "mortar")),
    "brick_wall": SystemSpec("دیوار آجری", ("bricks", "mortar", "reinforcement",
                                         "lintels", "openings"), ("bricks", "mortar")),
    "plaster_finish": SystemSpec("گچ و خاک و سفیدکاری", ("base_plaster", "finish_plaster",
                                                     "mesh", "corners", "openings"),
                                ("base_plaster", "finish_plaster")),
    "ceramic_finish": SystemSpec("کاشی و سرامیک", ("tiles", "adhesive_mortar", "grout",
                                                "skirting", "openings"), ("tiles", "adhesive_mortar")),
    "paint_finish": SystemSpec("رنگ‌آمیزی", ("primer", "base_coats", "finish_coats",
                                          "prep_work"), ("finish_coats",)),
    "waterproofing": SystemSpec("عایق‌کاری", ("base_layer", "membrane", "laps",
                                           "corners", "penetrations"), ("membrane",)),
    "floor_finish": SystemSpec("کف‌سازی", ("subbase", "screed", "surface", "skirting"),
                                         ("surface",)),
    "door_window": SystemSpec("درب و پنجره", ("frame", "glazing", "hardware",
                                              "installation"), ("frame",)),
    "plumbing": SystemSpec("لوله‌کشی", ("pipes", "fittings", "valves", "insulation",
                                       "supports", "equipment"), ("pipes",)),
    "hvac": SystemSpec("گرمایش، سرمایش و تهویه", ("ducts", "pipes", "fittings",
                                                  "insulation", "supports", "equipment"),
                       ("equipment",)),
    "fire_protection": SystemSpec("اطفای حریق", ("pipes", "fittings", "sprinklers",
                                                "valves", "supports", "equipment"),
                                 ("pipes",)),
    "electrical_power": SystemSpec("برق و توزیع نیرو", ("cables", "conduits", "trays",
                                                     "boards", "sockets", "earthing"),
                                   ("cables",)),
    "lighting": SystemSpec("روشنایی", ("cables", "conduits", "fixtures", "switches",
                                    "supports"), ("fixtures",)),
    "low_voltage": SystemSpec("جریان ضعیف", ("cables", "conduits", "devices",
                                           "termination", "racks"), ("devices",)),
}

# Only these canonical formula routes may be calculated in this review workflow.
# Other details require explicit measured amounts, not the approximate roof formulas.
_ENGINE_FIELDS = {
    ("building", "shear_wall"): ("length", "thickness", "height", "count"),
    ("building", "stair_concrete"): ("sloped_length", "width", "waist_thickness", "count"),
    ("building", "solid_slab_roof"): ("length", "width", "thickness", "count"),
    ("building", "rebar"): ("length", "unit_weight", "count"),
    ("building", "plaster"): ("length", "height", "openings", "count"),
    ("building", "paint"): ("length", "height", "openings", "count"),
    ("building", "tile"): ("length", "height", "openings", "waste"),
    ("advanced", "steel_roof_deck_area"): ("length", "width", "count"),
    ("advanced", "steel_roof_deck_weight"): ("length", "width", "sheet_weight", "count"),
    ("advanced", "footing_concrete"): ("length", "width", "thickness", "count"),
    ("advanced", "screed"): ("length", "width", "thickness", "count"),
    ("mechanical", "pipe"): ("length", "count"),
    ("mechanical", "duct_area"): ("width", "height", "length"),
    ("mechanical", "equipment"): ("count",),
    ("electrical", "cable"): ("length", "count"),
    ("electrical", "conduit"): ("length", "count"),
    ("electrical", "panel"): ("count",),
    ("electrical", "light"): ("count",),
    ("electrical", "cable_tray"): ("length",),
}


def _id(kind: str, floor: str, name: str) -> str:
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return json.dumps([x.translate(digits).casefold().strip() for x in (kind, floor, name)],
                      ensure_ascii=False, separators=(",", ":"))


def empty_system(kind: str, floor_id: str, system_id: str) -> dict:
    if kind not in SPECS:
        raise KeyError(f"نوع عملیات پشتیبانی‌نشده است: {kind}")
    return {"kind": kind, "floor_id": require_text(floor_id, "طبقه"),
            "system_id": require_text(system_id, "شناسه سیستم"),
            "source": {}, "components": {name: {"status": "unreviewed"}
                                         for name in SPECS[kind].components}}


def _preview_component(component: dict, name: str, engine: TakeoffEngine) -> list[dict]:
    if not isinstance(component, dict):
        raise ValueError("ساختار جزء نامعتبر است")
    status = component.get("status")
    if status == "not_applicable":
        require_text(component.get("reason"), f"دلیل عدم کاربرد {name}")
        require_text(component.get("source_ref"), f"مرجع بررسی {name}")
        require_text(component.get("approved_by"), f"تأییدکننده عدم کاربرد {name}")
        return []
    if status != "confirmed":
        raise ValueError(f"{name} هنوز تأیید نشده است")
    require_text(component.get("approved_by"), f"تأییدکننده {name}")
    data = component.get("items")
    if not isinstance(data, list) or not data:
        raise ValueError("جزء تأییدشده باید ریزاقلام مستقل داشته باشد")
    seen = set()
    rows = []
    for n, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError("ساختار ریزقلم نامعتبر است")
        line = require_text(item.get("line_id"), "شناسه ردیف")
        if line in seen:
            raise ValueError("ردیف اندازه‌گیری تکراری است")
        seen.add(line)
        evidence = require_text(item.get("source_ref"), "مرجع اندازه‌گیری")
        description = require_text(item.get("description"), "شرح ریزقلم")
        declared_domain = require_text(item.get("domain"), "حوزه تخصصی ریزقلم")
        if declared_domain not in TakeoffEngine.DOMAINS:
            raise ValueError("حوزه تخصصی ریزقلم معتبر نیست")
        code = require_text(item.get("item_code"), "کد عملیات")
        mode = item.get("mode")
        if mode == "engine":
            route = (item.get("domain"), item.get("item"))
            required = _ENGINE_FIELDS.get(route)
            if required is None:
                raise ValueError("فرمول موجود برای این ریزقلم معتبر/تأییدشده نیست")
            params = item.get("params")
            if not isinstance(params, dict) or set(params) != set(required):
                raise ValueError("ورودی‌های فرمول ناقص یا دارای مقدار اضافی‌اند")
            for key, value in params.items():
                positive(value, key, allow_zero=(key in {"openings"}), integer=(key == "count"))
            computed = engine.calculate(*route, description=description, source=evidence, **params)
            amount, unit, formula = computed.quantity, computed.unit, computed.formula
        elif mode == "measured":
            amount = positive(item.get("quantity"), "مقدار اندازه‌گیری‌شده")
            unit = normalize_unit(require_text(item.get("unit"), "واحد متره"))
            formula = require_text(item.get("formula"), "مبنای هندسی/شمارش")
            require_text(item.get("measurement_ref"), "مرجع مستقل اندازه‌گیری")
        else:
            raise ValueError("شیوه متره فقط محاسبه مستند یا مقدار بازبینی‌شده است")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("مقدار جزئی باید مثبت و متناهی باشد")
        rows.append({"line_id": line, "source_ref": evidence, "description": description,
                     "item_code": code, "domain": declared_domain,
                     "quantity": amount, "unit": unit, "formula": formula,
                     "params": deepcopy(item.get("params") or {}),
                     "method": mode})
    return rows


def preview_system(data: dict, engine: TakeoffEngine) -> dict:
    if not isinstance(data, dict) or data.get("kind") not in SPECS:
        raise ValueError("نوع سیستم متره معتبر نیست")
    kind = data["kind"]
    floor = require_text(data.get("floor_id"), "طبقه")
    identity = require_text(data.get("system_id"), "شناسه سیستم")
    source = data.get("source", {})
    blockers = []
    rows = []
    try:
        sid = _validate_source(source, identity)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        sid = ""
        blockers.append(f"منبع: {exc}")
    spec = SPECS[kind]
    components = data.get("components")
    if not isinstance(components, dict) or set(components) != set(spec.components):
        raise ValueError("فهرست گروه‌های مصالح یا عملیات با نوع سیستم تطبیق ندارد")
    seen = set()
    adjustments = {
        "waffle": {"junction_adjustment": "ribs_y"},
        "uboot": {"verified_voids": "gross_concrete"},
        "cobiax": {"verified_voids": "gross_concrete"},
    }.get(kind, {})
    adjustment_rows = {}
    for name in spec.components:
        part = components[name]
        try:
            if name in spec.essential and isinstance(part, dict) and part.get("status") == "not_applicable":
                raise ValueError("این جزء برای تیپ انتخابی ضروری است؛ عدم کاربرد مجاز نیست")
            accepted_rows = _preview_component(part, name, engine)
            if name == "openings":
                # Openings are evidence, not additional billable quantities.
                # Users must enter *net* quantities for their other components.
                if accepted_rows and part.get("net_excluded_from_quantities") is not True:
                    raise ValueError("بازشوها باید از ریزمقادیر خالص کسر و صریحاً تأیید شده باشند")
                adjustment_rows[name] = accepted_rows
                continue
            if name in adjustments:
                adjustment_rows[name] = accepted_rows
                continue
            for item in accepted_rows:
                allowed_domains = (
                    {"mechanical"} if kind in {"plumbing", "hvac", "fire_protection"}
                    else {"electrical"} if kind in {"electrical_power", "lighting", "low_voltage"}
                    else {"building", "advanced"}
                )
                if item["domain"] not in allowed_domains:
                    raise ValueError("حوزه ردیف با نوع عملیات ساختمان ناسازگار است")
                ref = f"aec:{kind}:{floor}:{identity}:{name}:{item['line_id']}"
                if ref in seen:
                    raise ValueError("شناسه ردیف پروژه تکراری است")
                seen.add(ref)
                rows.append({**item, "source_id": ref, "category": spec.title,
                             "system": floor, "component": name})
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            blockers.append(f"{spec.title} / {name}: {exc}")
    # A concrete void/intersection is a DEDUCTION, never a positive BOQ row.
    for deduction_component, target_component in adjustments.items():
        checked = adjustment_rows.get(deduction_component)
        if not checked:
            continue
        targets = [r for r in rows if r["component"] == target_component]
        if len(targets) != 1 or len(checked) != 1:
            blockers.append("کسر حجم نیازمند دقیقاً یک ردیف ناخالص و یک ردیف کسر مستند است")
            continue
        source, target = checked[0], targets[0]
        if target["unit"] != "m3" or source["unit"] != "m3":
            blockers.append("کسر حجم سقف باید بر حسب مترمکعب و هم‌واحد با بتن باشد")
            continue
        net = target["quantity"] - source["quantity"]
        if net <= 0 or not math.isfinite(net):
            blockers.append("حجم خالص سقف پس از کسورات نامعتبر است")
            continue
        target["params"]["gross_m3"] = target["quantity"]
        target["params"]["deduction"] = {
            "quantity_m3": source["quantity"], "source_ref": source["source_ref"],
            "measurement_formula": source["formula"],
        }
        target["quantity"] = net
        target["formula"] = target["formula"] + " − کسر حجم مستند " + source["formula"]
    return {"kind": kind, "floor_id": floor, "system_id": identity, "source_id": sid,
            "ready": not blockers, "blockers": blockers, "rows": rows,
            "preview_only": True}


class ReviewedAECWorkflow:
    """SQLite-backed reviewed multi-discipline system, preserving prior takeoffs."""

    def __init__(self, store: Any, engine: TakeoffEngine):
        self.store, self.engine = store, engine

    def _get_project(self, pid: str) -> tuple[dict, str]:
        digest = self.store.current_digest(pid)
        if hasattr(self.store, "_cache"):
            self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        return project, digest

    def get(self, pid: str, kind: str, floor: str, sid: str) -> dict | None:
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        return deepcopy((project.get(REGISTER) or {}).get(_id(kind, floor, sid)))

    def save_draft(self, pid: str, data: dict, *, expected_revision: int = 0) -> dict:
        if not isinstance(data, dict) or data.get("kind") not in SPECS:
            raise ValueError("نوع سیستم ناشناخته است")
        kind, floor, sid = data["kind"], require_text(data.get("floor_id"), "طبقه"), require_text(data.get("system_id"), "شناسه سیستم")
        if not isinstance(data.get("components"), dict) or set(data["components"]) != set(SPECS[kind].components):
            raise ValueError("ساختار گروه‌های متره ناقص است")
        source = data.get("source", {})
        if source:
            _validate_source(source, sid)
        try:
            json.dumps(data, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("اطلاعات متره قابل ذخیره‌سازی نیست") from exc
        project, digest = self._get_project(pid)
        register = project.setdefault(REGISTER, {})
        if not isinstance(register, dict):
            raise ValueError("دفتر ثبت متره AEC نامعتبر است")
        key = _id(kind, floor, sid)
        old = register.get(key)
        if old and old.get("status") == "committed":
            raise ValueError("سیستم قبلاً به متره قطعی منتقل شده است")
        revision = old["revision"] if old else 0
        if expected_revision != revision:
            raise RuntimeError("تعارض نسخه؛ اطلاعات را دوباره بارگذاری کنید")
        if old and old["data"].get("source") != source:
            if any(isinstance(x, dict) and x.get("status") in ("confirmed", "not_applicable")
                   for x in data["components"].values()):
                raise ValueError("منبع متره تغییر کرده؛ تأییدهای قبلی باید بازنشانی شوند")
        source_id = source.get("source_id") if isinstance(source, dict) else None
        if source_id:
            for registry_name in (REGISTER, "beam_detail_register", "reviewed_structural_members"):
                for other_key, record in (project.get(registry_name) or {}).items():
                    if registry_name == REGISTER and other_key == key:
                        continue
                    if record.get("data", {}).get("source", {}).get("source_id") == source_id:
                        raise ValueError("منبع اندازه‌گیری برای چند عضو تکرار شده است")
        entry = {"status": "draft", "revision": revision + 1, "data": deepcopy(data),
                 "updated_at": datetime.now(timezone.utc).isoformat()}
        register[key] = entry
        self.store.save(pid, project, expected_digest=digest)
        return deepcopy(entry)

    def preview(self, pid: str, kind: str, floor: str, sid: str) -> dict:
        found = self.get(pid, kind, floor, sid)
        if not found:
            raise KeyError(sid)
        out = preview_system(found["data"], self.engine)
        out["revision"] = found["revision"]
        out["committed"] = found["status"] == "committed"
        return out

    def commit(self, pid: str, kind: str, floor: str, sid: str, *, expected_revision: int) -> dict:
        project, digest = self._get_project(pid)
        reg = project.get(REGISTER) or {}
        record = reg.get(_id(kind, floor, sid))
        if record is None:
            raise KeyError(sid)
        if record["status"] == "committed":
            raise ValueError("متره قبلاً ثبت قطعی شده است")
        if record["revision"] != expected_revision:
            raise RuntimeError("تعارض نسخه؛ ثبت قطعی ممنوع")
        out = preview_system(record["data"], self.engine)
        if not out["ready"]:
            raise ValueError("دیتایل یا تأیید ناقص است؛ ثبت قطعی متوقف شد: " + "؛ ".join(out["blockers"]))
        existing = project.get("takeoffs") or []
        old_ids = {x.get("source_id") for x in existing}
        new_ids = {x["source_id"] for x in out["rows"]}
        if old_ids & new_ids or out["source_id"] in old_ids:
            raise ValueError("ریزمتره تکراری است")
        if len(new_ids) != len(out["rows"]):
            raise ValueError("شناسه ریزمتره تکراری است")
        takeoffs = deepcopy(existing)
        for row in out["rows"]:
            takeoffs.append({
                "id": row["source_id"], "member_code": sid, "source_id": row["source_id"],
                "domain": row["domain"], "item": row["item_code"], "system": floor,
                "description": row["description"], "params": row["params"],
                "provenance": deepcopy(record["data"]["source"]),
                "review": {"approved_by": record["data"]["components"][row["component"]]["approved_by"],
                           "component": row["component"], "method": row["method"],
                           "measurement_source": row["source_ref"]},
                "revision": record["revision"],
                "quantities": [{"code": row["item_code"], "title": row["description"],
                                "system": floor, "unit": row["unit"],
                                "amount": row["quantity"], "formula": row["formula"],
                                "price_code": None, "unit_price": None}]
            })
        boq_data = []
        for takeoff in takeoffs:
            for quantity in takeoff.get("quantities", []):
                boq_data.append({
                    "source": takeoff.get("source_id"), "source_id": takeoff.get("source_id"),
                    "source_type": "takeoff", "description": quantity.get("title"),
                    "quantity": quantity.get("amount"), "unit": quantity.get("unit"),
                    "item_code": quantity.get("code"), "price_code": quantity.get("price_code"),
                    "unit_price": quantity.get("unit_price"), "category": takeoff.get("domain"),
                    "group": takeoff.get("system") or takeoff.get("domain"),
                })
        project["boq"] = build_boq(boq_data)
        project["takeoffs"] = takeoffs
        record["status"] = "committed"
        record["committed_at"] = datetime.now(timezone.utc).isoformat()
        record["source_ids"] = sorted(new_ids)
        self.store.save(pid, project, expected_digest=digest)
        return {"status": "committed", "revision": record["revision"],
                "takeoff_rows": len(out["rows"]), "source_ids": sorted(new_ids)}
