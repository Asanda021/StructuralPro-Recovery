"""Validated bridge from graphical drawing sessions to persistent takeoff/BOQ rows.

The bridge is intentionally deterministic: it never invents scale, quantities, or
price data. Callers must validate the session and explicitly select rows to commit.
"""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.graphical_takeoff import Point, polygon_area, polyline_length


_KIND_UNITS = {"length": "m", "area": "m2", "count": "عدد"}


def verified_measurement_identities(record: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bind commit-time source bytes and per-page evidence to stable measurements."""
    payload = record.get("session", {})
    expected = str(record.get("source_sha256") or "")
    path = Path(str(payload.get("drawing_source", "")))
    if not expected or not path.is_file():
        raise ValueError("منشأ فایل و SHA-256 متره احراز نشده؛ منبع را بازبینی و دوباره اندازه‌گیری کنید")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected or payload.get("source_sha256") != expected:
        raise ValueError("فایل منبع نقشه پس از اندازه‌گیری تغییر کرده است؛ ثبت متره رد شد")
    if path.suffix.lower() == ".pdf":
        import fitz
        with fitz.open(stream=data, filetype="pdf") as document:
            for row in rows:
                page = int(row["page"])
                if not 1 <= page <= len(document) or not document[page-1].get_drawings():
                    raise ValueError("صفحه PDF فاقد شاهد برداری معتبر است؛ کمیت رستری وارد BOQ نمی‌شود")
                bounds=document[page-1].rect
                if row.get("geometry_evidence") and any(not (0<=float(x)<=math.ceil(bounds.width*150/72) and 0<=float(y)<=math.ceil(bounds.height*150/72)) for x,y in row["geometry"]):
                    raise ValueError("هندسه خارج از صفحه نقشه است")
    else:
        from core.drawings.viewer_model import DrawingViewerModel
        try:
            DrawingViewerModel(path)
        except Exception as exc:
            raise ValueError("منبع CAD/BIM با واردکننده اصلی معتبر شناخته نشد") from exc
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("فایل نقشه هنگام بررسی منشأ تغییر کرده است")
    items = {str(item["id"]): item for item in payload.get("items", [])}
    def canonical(points, closed=False):
        points = tuple(tuple(float(v) for v in point) for point in points)
        if closed:
            from core.drawings.planar_geometry import canonical_ring
            return canonical_ring(points)
        variants = [points, points[::-1]]
        if closed and points:
            variants = (variant[i:]+variant[:i] for variant in variants for i in range(len(variant)))
        return min(variants)
    seen = set()
    for row in rows:
        calibration = (payload.get("calibrations", {}) or {}).get(str(row["page"]))
        if calibration is None and row["kind"] in {"length", "area"}:
            raise ValueError("کالیبراسیون صریح صفحه احراز نشده است")
        identity = {"source_sha256": actual, "page": row["page"], "kind": row["kind"],
                    "operation": row["item_code"], "unit": row["unit"],
                    "geometry": canonical(row["geometry"], row["kind"] == "area"),
                    "holes": sorted(canonical(hole, True) for hole in row.get("holes", [])),
                    # Scale and display counters cannot turn the same physical
                    # source/geometry/operation into an independent measurement.
                    "measurement_context": str(items[row["takeoff_id"]].get("source", "")) if row["kind"] == "count" and not row["geometry"] else ""}
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if fingerprint in seen:
            raise ValueError("متره تکراری با هندسه و منشأ یکسان در انتخاب فعلی وجود دارد")
        seen.add(fingerprint)
        row.update(source_sha256=actual, measurement_identity=fingerprint, calibration=calibration)
    return rows


def assert_new_measurements(project: dict[str, Any], record: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    from core.drawings.roof_region import reject_reserved_regions
    reject_reserved_regions(project,record,rows)
    from core.drawings.planar_geometry import measurement_overlap
    candidates=[]
    for old in project.get('takeoffs',[]):
        p=old.get('params') or {}
        if old.get('domain')=='drawing' and old.get('item')=='area':
            candidates.append({**p,'kind':'area'})
    for row in rows:
        if row['kind']=='area':
            meta=row.get('geometry_evidence')
            if meta and not meta.get('quantity_owner','').strip():raise ValueError('مالک مقدار و مرجع آن برای ثبت برداشت چندضلعی الزامی است')
            if meta and (not meta.get('floor_id','').strip() or not meta.get('member_id','').strip() or not project.get('floors') or not project.get('members')):
                raise ValueError('شناسه طبقه و عضو ثبت‌شده پروژه برای انتقال چندضلعی به BOQ الزامی است')
            if meta and project.get('floors'):
                from core.projects.project_model import _identity
                floor=_identity(meta.get('floor_id',''));member=_identity(meta.get('member_id',''))
                if floor not in {_identity(f['id']) for f in project['floors']} or not any(_identity(m['id'])==member and _identity(m['floor_id'])==floor for m in project.get('members',[])):
                    raise ValueError('عضو و طبقه برداشت با هویت صریح پروژه مطابقت ندارند')
            for old in candidates:
                old_meta=old.get('geometry_evidence') or {}
                if meta and old_meta and meta.get('floor_id') and meta.get('member_id'):
                    from core.projects.project_model import _identity
                    if all(_identity(meta[k])==_identity(old_meta.get(k,'')) for k in ('floor_id','member_id')):
                        raise ValueError('عضو فیزیکی قبلاً متره شده است؛ نسخه جدید نقشه نیازمند اصلاحیه رسمی است')
                if (row.get('geometry_evidence') or old.get('geometry_evidence')) and row.get('source_sha256')==old.get('source_sha256') and row.get('page')==old.get('page'):
                    if measurement_overlap(row,old):
                        raise ValueError('هم‌پوشانی برداشت با مالکیت نامعلوم؛ بازبینی مستقل پیش از پرداخت لازم است')
            candidates.append(row)
    known = {(row.get("params") or {}).get("measurement_identity") for row in project.get("takeoffs", [])}
    if any(row["measurement_identity"] in known for row in rows):
        raise ValueError("اندازه‌گیری با همین منشأ و هندسه قبلاً در نشست دیگری ثبت شده؛ دوباره‌شماری رد شد")
    source = Path(str(record.get("drawing_source", ""))).resolve()
    sessions = project.get("drawing_sessions", {}) or {}
    for old in project.get("takeoffs", []):
        if old.get("domain") not in {"drawing", "drawing_ai"}: continue
        params = old.get("params") or {}
        old_session = sessions.get(str(old.get("drawing_session_id", "")), {}) or {}
        old_source = params.get("drawing_source") or old_session.get("drawing_source")
        if old_source and Path(str(old_source)).resolve() == source:
            if not params.get("measurement_identity") or not params.get("source_sha256"):
                raise ValueError("متره قدیمی این نقشه فاقد منشأ قابل احراز است؛ پیش از ثبت جدید بازبینی کنید")
            if params["source_sha256"] != record["source_sha256"]:
                raise ValueError("نسخه جدید نقشه باید با متره پرداختی نسخه قبلی تطبیق و بازبینی شود")


def validate_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a serialized session and return a compact, user-readable report."""
    issues: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "issues": ["داده نشست متره باید یک شیء معتبر باشد"]}
    try:
        session = DrawingTakeoffSession.from_dict(payload)
        report = session.validate()
        issues.extend(report.get("issues", []))
        if not str(session.drawing_source).strip():
            issues.append("مسیر/شناسه منبع نقشه ثبت نشده است")
        for item in session.items:
            if item.kind not in _KIND_UNITS:
                issues.append(f"نوع متره {item.id} پشتیبانی نمی‌شود")
            elif item.unit != _KIND_UNITS[item.kind]:
                issues.append(f"واحد متره {item.id} با نوع آن سازگار نیست")
            expected_ref = f"{session.drawing_source}#page={item.page}&takeoff={item.id}"
            if not item.source_ref.strip() or item.source_ref != expected_ref:
                issues.append(f"مرجع صفحه/ناحیه برای متره {item.id} با منبع ذخیره‌شده مطابقت ندارد")
            if item.kind in {"length", "area"} and not item.formula.strip():
                issues.append(f"فرمول اندازه‌گیری متره {item.id} ثبت نشده است")
            if item.kind == "length" and len(item.geometry) < 2:
                issues.append(f"هندسه متره طول {item.id} ناقص است")
            if item.kind == "area" and len(item.geometry) < 3:
                issues.append(f"هندسه متره مساحت {item.id} ناقص است")
            for point in item.geometry:
                if len(point) != 2 or any(not math.isfinite(float(value)) for value in point):
                    issues.append(f"مختصات هندسه متره {item.id} نامعتبر است")
                    break
            if item.kind == "count" and (item.quantity <= 0 or not float(item.quantity).is_integer()):
                issues.append(f"تعداد متره {item.id} باید عدد صحیح مثبت باشد")
            if item.kind in {"length", "area"} and item.page in session.calibrations:
                factor = session.calibrations[item.page].meters_per_pixel
                points = [Point(*point) for point in item.geometry]
                if item.kind == "area" and item.geometry_evidence is not None:
                    meta=item.geometry_evidence
                    if not isinstance(meta,dict):raise ValueError("قرارداد هندسه نامعتبر است")
                    verified=session._polygon_evidence(item.geometry,item.holes,item.page,meta.get("opening_refs",[]),
                        topology=meta.get('policy','exact_simple_polygon_v1'),**{k:meta.get(k,'') for k in ('floor_id','member_id','quantity_owner')})
                    if meta!=verified or item.quantity!=float(verified["net_m2"]):
                        raise ValueError("مقدار دقیق یا مدارک هندسه با رأس‌ها و مقیاس مطابقت ندارد")
                    continue
                if item.kind == "length":
                    expected = polyline_length(points) * factor
                else:
                    holes = [[Point(*point) for point in hole] for hole in item.holes]
                    if any(len(hole) < 3 for hole in holes):
                        issues.append(f"هندسه بازشو متره {item.id} ناقص است")
                    net = polygon_area(points) - sum(polygon_area(hole) for hole in holes)
                    expected = net * factor * factor
                if expected <= 0 or not math.isclose(item.quantity, expected, rel_tol=1e-9, abs_tol=1e-9):
                    issues.append(f"مقدار متره {item.id} با هندسه و کالیبراسیون ثبت‌شده مطابقت ندارد")
    except Exception as exc:
        issues.append(f"نشست متره قابل بازیابی/اعتبارسنجی نیست: {exc}")
    return {"valid": not issues, "issues": list(dict.fromkeys(issues))}


def session_to_boq_rows(
    payload: dict[str, Any],
    *,
    session_id: str,
    selected_item_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert only explicitly selected, validated drawing items into BOQ inputs."""
    report = validate_session_payload(payload)
    if not report["valid"]:
        raise ValueError("نشست نقشه معتبر نیست: " + "؛ ".join(report["issues"]))
    session = DrawingTakeoffSession.from_dict(payload)
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("شناسه پایدار نشست نقشه الزامی است")
    selected = None if selected_item_ids is None else {str(x) for x in selected_item_ids}
    if selected is not None and not selected:
        raise ValueError("برای انتقال به BOQ باید دست‌کم یک متره صریحاً انتخاب شود")
    known = {item.id for item in session.items}
    if selected is not None:
        unknown = selected - known
        if unknown:
            raise ValueError("شناسه متره در نشست وجود ندارد: " + "، ".join(sorted(unknown)))
    rows: list[dict[str, Any]] = []
    for item in session.items:
        if selected is not None and item.id not in selected:
            continue
        if item.quantity <= 0:
            raise ValueError(f"مقدار متره {item.id} باید برای ورود به BOQ مثبت باشد")
        rows.append({
            "takeoff_id": item.id,
            "source_id": f"drawing:{sid}:{item.id}",
            "source": item.source_ref,
            "source_type": "drawing_takeoff",
            "drawing_source": session.drawing_source,
            "page": item.page,
            "kind": item.kind,
            "description": item.label.strip() or item.takeoff_code.strip() or item.kind,
            "quantity": item.geometry_evidence["net_m2"] if item.geometry_evidence else float(item.quantity),
            "geometry_evidence": item.geometry_evidence,
            "unit": item.unit,
            "item_code": item.takeoff_code.strip() or f"DRAW-{item.kind.upper()}",
            "price_code": item.takeoff_code.strip() or None,
            "unit_price": None,
            "formula": item.formula,
            "geometry": [list(point) for point in item.geometry],
            "holes": [[list(point) for point in hole] for hole in item.holes],
            "confidence": float(item.confidence),
            "needs_confirmation": False,
        })
    if not rows:
        raise ValueError("هیچ متره‌ای برای انتقال به BOQ انتخاب نشده است")
    return rows


def build_takeoff_export_payload(session: DrawingTakeoffSession) -> dict[str, Any]:
    """Export a review handoff through the same validator used by project storage."""
    source = str(session.drawing_source).strip()
    validated = session_to_boq_rows(
        session.to_dict(), session_id=source,
        selected_item_ids=[item.id for item in session.items],
    )
    items_by_id = {item.id: item for item in session.items}
    rows = [{
        "source_id": f"drawing:{source}:page:{row['page']}:{row['takeoff_id']}",
        "source_ref": row["source"], "page": row["page"], "kind": row["kind"],
        "quantity": row["quantity"], "unit": row["unit"],
        "description": row["description"], "formula": row["formula"],
        "takeoff_code": items_by_id[row["takeoff_id"]].takeoff_code,
        "status": "needs_review",
    } for row in validated]
    from core.commercial.exact_values import exact,number,wire
    @exact
    def total(unit):
        return wire(sum((number(row['quantity'],'مقدار هندسی') for row in validated if row['unit']==unit),number(0,'صفر')))
    return {
        "schema": "structuralpro.drawing-takeoff.v1",
        "drawing_source": source, "approval_required": True, "items": rows,
        "summary": {
            "items": len(rows), "needs_review": len(rows),
            "by_unit": {
                unit: total(unit)
                for unit in sorted({row["unit"] for row in rows})
            },
        },
    }
