"""Independent, non-payable steel stair engineering preflight.

This does NOT register the stair into generic AEC, price, BOQ or commit routes.
It checks documented physical schedules and proposed payer identity, leaving
cross-member ownership and structural design acceptance explicitly blocked.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, localcontext
import re
from core.takeoff.bored_pile_ownership_preflight import _canonical

POLICY = "stair_metal_ownership_preflight_v1"
GROUP_UNITS = {
    "stringers": "kg", "treads": "kg", "landings": "kg",
    "connection_plates": "kg", "supports": "kg", "anchors": "عدد",
    "bolts": "عدد", "welds": "m", "railings": "kg",
    "coating": "m2", "fireproofing": "m2",
}
REQUIRED = frozenset(("stringers", "treads"))
MODES = {
    "steel_profile_schedule": "kg", "steel_plate_schedule": "kg",
    "piece_schedule": "عدد", "measured": None,
}
MAX_ENTRIES = 512


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: independent documented reference is required")
    return value.strip()


def _number(value, field, *, integer=False):
    if isinstance(value, (float, bool)):
        raise ValueError(f"{field}: input must be documented exact decimal, not float/bool")
    if not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{field}: quantity must be decimal text")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field}: invalid decimal") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{field}: strictly positive finite value required")
    if integer and result != result.to_integral_value():
        raise ValueError(f"{field}: independent whole-piece count required")
    if len(result.as_tuple().digits) > 120 or abs(result.adjusted()) > 120:
        raise ValueError(f"{field}: input precision/range not supported by preflight")
    return result


def _strict_keys(obj, keys, label):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError(f"{label}: unexpected or missing fields")


def _quantity(entry, unit):
    method = entry["mode"]
    if method not in MODES:
        raise ValueError("stair quantity mode is not approved")
    if MODES[method] is not None and MODES[method] != unit:
        raise ValueError("stair material and calculation method mismatch")
    values = entry["details"]
    if method == "steel_profile_schedule":
        _strict_keys(values, ("count", "length_m", "unit_weight_kg_m", "unit_weight_source"), "profile detail")
        _text(values["unit_weight_source"], "unit weight reference")
        return (_number(values["count"], "count", integer=True) *
                _number(values["length_m"], "length") *
                _number(values["unit_weight_kg_m"], "certified kg/m"))
    if method == "steel_plate_schedule":
        _strict_keys(values, ("count", "length_m", "width_m", "thickness_m", "density_kg_m3", "density_source"), "plate detail")
        _text(values["density_source"], "density reference")
        return (_number(values["count"], "count", integer=True) *
                _number(values["length_m"], "length") *
                _number(values["width_m"], "width") *
                _number(values["thickness_m"], "thickness") *
                _number(values["density_kg_m3"], "documented density"))
    if method == "piece_schedule":
        _strict_keys(values, ("count",), "piece detail")
        return _number(values["count"], "piece count", integer=True)
    if method == "measured":
        _strict_keys(values, ("quantity", "unit", "measurement_ref", "basis"), "measured detail")
        _text(values["measurement_ref"], "independent measurement reference")
        _text(values["basis"], "basis of measurement")
        if values["unit"] != unit:
            raise ValueError("physical unit mismatch")
        return _number(values["quantity"], "measured quantity", integer=(unit == "عدد"))
    raise ValueError("unapproved quantity method")


def _preview_exact(document):
    """Return a non-payable *candidate* schedule; fail-closed on any missing claim.

    Project-wide duplicate identity, complete support ownership, structural
    engineering approval and payment decisions are never inferred here.
    """
    result = {"kind": "stair_metal", "engineering_ready": False, "ready": False,
              "commit_allowed": False, "payable_rows": [], "candidates": [],
              "totals_exact": {}, "blockers": []}
    try:
        _strict_keys(document, ("kind", "measurement_policy", "building_id", "floor_id",
                                "system_id", "axis", "source", "groups", "ownership"), "steel stair contract")
        if document["kind"] != "stair_metal" or document["measurement_policy"] != POLICY:
            raise ValueError("independent steel-stair policy required; concrete stair not interchangeable")
        for key in ("building_id", "floor_id", "system_id", "axis"):
            _text(document[key], key)
        source = document["source"]
        _strict_keys(source, ("plan_ref", "detail_ref", "sha256", "source_id"), "source")
        for key in ("plan_ref", "detail_ref", "source_id"):
            _text(source[key], key)
        if not isinstance(source["sha256"], str) or not re.fullmatch(r"[a-fA-F0-9]{64}", source["sha256"]):
            raise ValueError("drawing file SHA-256 is required")
        groups = document["groups"]
        _strict_keys(groups, GROUP_UNITS, "all steel-stair groups")
        seen = set()
        calculated = []
        totals = defaultdict(Decimal)
        for group_name, unit in GROUP_UNITS.items():
            group = groups[group_name]
            _strict_keys(group, ("status", "approved_by", "source_ref", "reason", "entries"), f"{group_name} group")
            for name in ("approved_by", "source_ref"):
                _text(group[name], f"{group_name} {name}")
            entries = group["entries"]
            if group["status"] == "not_applicable":
                if group_name in REQUIRED:
                    raise ValueError(f"essential steel stair group {group_name} cannot be omitted")
                _text(group["reason"], "documented non-applicability reason")
                if entries != []:
                    raise ValueError("not-applicable group cannot own physical entries")
                continue
            if group["status"] != "confirmed" or not isinstance(entries, list) or not 0 < len(entries) <= MAX_ENTRIES:
                raise ValueError(f"group {group_name} requires independent reviewed components")
            for entry in entries:
                _strict_keys(entry, ("id", "source_ref", "approved_by", "spec_ref", "scope_ref", "mode", "details"), "physical part")
                physical_id = _text(entry["id"], "physical id")
                if _canonical(physical_id) in seen:
                    raise ValueError("duplicate physical id across steel-stair groups")
                seen.add(_canonical(physical_id))
                for field in ("source_ref", "approved_by", "spec_ref", "scope_ref"):
                    _text(entry[field], field)
                qty = _quantity(entry, unit)
                if qty <= 0 or not qty.is_finite():
                    raise ValueError("physical quantity must remain finite and positive")
                if abs(qty.adjusted()) > 120:
                    raise ValueError("calculated quantity exceeds bounded engineering preflight range")
                totals[unit] += qty
                calculated.append({"physical_id": physical_id, "component": group_name,
                                   "quantity_exact": str(qty), "unit": unit,
                                   "source_ref": entry["source_ref"], "scope_ref": entry["scope_ref"],
                                   "method": entry["mode"]})
        claims = document["ownership"]
        _strict_keys(claims, ("ledger_ref", "claims"), "proposed ownership")
        _text(claims["ledger_ref"], "project-wide ownership ledger reference")
        if not isinstance(claims["claims"], list) or len(claims["claims"]) != len(calculated):
            raise ValueError("every physical component needs one explicit ownership claim")
        claim_ids = set()
        for claim in claims["claims"]:
            _strict_keys(claim, ("physical_id", "building_id", "owner_system", "payer_system", "scope_ref", "source_ref", "approved_by"), "ownership claim")
            physical_id = _text(claim["physical_id"], "owned physical id")
            if _canonical(physical_id) in claim_ids:
                raise ValueError("duplicate proposed payer/physical id")
            claim_ids.add(_canonical(physical_id))
            for field in ("building_id", "owner_system", "payer_system", "scope_ref", "source_ref", "approved_by"):
                _text(claim[field], field)
            if claim["building_id"] != document["building_id"]:
                raise ValueError("physical component ownership crosses project identity")
            if claim["owner_system"] != document["system_id"]:
                raise ValueError("steel stair member is not owned by documented stair system")
            if claim["payer_system"] != document["system_id"]:
                raise ValueError("claimed payer is not the owning steel stair; external payer requires joint review")
            row = next((e for e in calculated if _canonical(e["physical_id"]) == _canonical(physical_id)), None)
            if row is None or row["scope_ref"] != claim["scope_ref"] or row["source_ref"] != claim["source_ref"]:
                raise ValueError("payer claim does not match measured physical scope")
        if claim_ids != seen:
            raise ValueError("incomplete ownership evidence for steel stair components")
        result["engineering_ready"] = True
        result["candidates"] = calculated
        result["totals_exact"] = {unit: str(n) for unit, n in sorted(totals.items())}
        result["blockers"].append("project-wide identity and ownership/payment crosscheck is still required; no BOQ commit allowed")
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        result["blockers"].append(str(exc))
    return result


def preview(document):
    """Run bounded exact arithmetic even for high-precision supplied schedules."""
    with localcontext() as ctx:
        ctx.prec = 1024
        return _preview_exact(document)
