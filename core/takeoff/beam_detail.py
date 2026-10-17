"""Reviewed beam-detail takeoff against the existing ProjectStore and TakeoffEngine.

Drafts remain in ProjectStore's SQLite-backed project payload.  Only a completely
reviewed beam can be atomically transferred to the existing takeoffs/BOQ path.
This module does NOT parse reinforcement or infer section dimensions from drawings.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from typing import Any

from core.takeoff.boq import build_boq
from core.takeoff.formulas import evaluate
from core.commercial.exact_values import number as exact_number, wire, exact
from core.takeoff.units import normalize_unit
from core.takeoff.commit_guards import require_source_unused, validate_commit_rows, rebuild_project_boq, require_reset_of_changed_approvals
from core.drawings.beam_detail_match import validate_evidence_link
from core.takeoff.stirrup_zones import validate_stirrup_zones
from core.takeoff.reviewed_components import cut_length as reviewed_cut_length, net_concrete, net_formwork


def component_fingerprint(row):
    from hashlib import sha256
    return sha256(json.dumps({k:v for k,v in row.items() if k not in ('review_status','reviewed_by','review_digest','approved_by')},sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def component_reviewed(row):
    if 'review_status' in row and (row.get('review_status')!='confirmed' or not row.get('reviewed_by') or row.get('review_digest')!=component_fingerprint(row)):raise ValueError('سری یا جزء نیازمند بازبینی معتبر پس از ویرایش است')

BAR_TYPES = ("longitudinal", "stirrups", "side_bars", "crossties", "additional")
BAR_LABELS = {
    "longitudinal": "میلگرد طولی", "stirrups": "خاموت", "side_bars": "کمرکش تیر",
    "crossties": "سنجاقی", "additional": "میلگرد تقویتی",
}
INITIAL_STATUSES = {
    "longitudinal": "needs_detail", "stirrups": "needs_detail", "side_bars": "unreviewed",
    "crossties": "unreviewed", "additional": "unreviewed",
}
VALID_STATUSES = frozenset({"needs_detail", "unreviewed", "needs_review", "confirmed", "not_applicable"})
REGISTER = "beam_detail_register"


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} الزامی است")
    return value.strip()


def _number(value: Any, label: str, *, zero: bool = False, integer: bool = False) -> float:
    if integer:
        n=exact_number(value,label,True)
        if n<n.__class__(0) or (n==0 and not zero) or n!=n.to_integral_value():raise ValueError(label+' باید صحیح و مثبت باشد')
        return int(n)
    if isinstance(value, bool):
        raise ValueError(f"{label} باید عدد معتبر باشد")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} باید عدد معتبر باشد") from exc
    if not math.isfinite(number) or number < 0 or (number == 0 and not zero):
        raise ValueError(f"{label} باید {'نامنفی' if zero else 'مثبت'} و متناهی باشد")
    if integer and not number.is_integer():
        raise ValueError(f"{label} باید عدد صحیح باشد")
    return number


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _beam_key(floor_id: str, beam_id: str) -> str:
    """One physical identity despite Latin/Persian digits or letter casing."""
    normalized = [" ".join(value.translate(_DIGITS).casefold().split())
                  for value in (floor_id, beam_id)]
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def empty_beam(floor_id: str, beam_id: str) -> dict[str, Any]:
    """Initial UI state: never convert 'unreviewed' to absent/zero."""
    return {
        "floor_id": _text(floor_id, "طبقه"), "beam_id": _text(beam_id, "شناسه تیر"),
        "source": {}, "geometry": {}, "formwork": {},
        "bars": {kind: {"status": status} for kind, status in INITIAL_STATUSES.items()},
    }


def _validate_identity(data: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(data, dict):
        raise ValueError("اطلاعات تیر باید ساختار معتبر داشته باشد")
    return _text(data.get("floor_id"), "طبقه"), _text(data.get("beam_id"), "شناسه تیر")


def _validate_source(source: dict[str, Any]) -> None:
    if not isinstance(source, dict):
        raise ValueError("ساختار منبع نقشه معتبر نیست")
    mode = source.get("mode")
    if mode not in {"manual", "drawing"}:
        raise ValueError("منبع باید دستی یا نقشه تأییدشده باشد")
    _text(source.get("source_id"), "شناسه یکتای برداشت")
    if mode == "drawing":
        digest = _text(source.get("sha256"), "اثر انگشت SHA-256 نقشه")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("SHA-256 نقشه باید ۶۴ رقم شانزده‌شانزدهی باشد")
        _number(source.get("page"), "صفحه نقشه", integer=True)


def _validate_bar_shape(bars: dict[str, Any]) -> None:
    if not isinstance(bars, dict) or set(bars) != set(BAR_TYPES):
        raise ValueError("وضعیت هر پنج قلم میلگرد باید جداگانه ثبت شود")
    for name, bar in bars.items():
        if not isinstance(bar, dict) or bar.get("status") not in VALID_STATUSES:
            raise ValueError(f"وضعیت {BAR_LABELS[name]} معتبر نیست")
        if "count" in bar:
            _number(bar["count"], "تعداد پیشنهادی میلگرد", integer=True)
        if "nominal_diameter_mm" in bar:
            nominal = _number(bar["nominal_diameter_mm"], "قطر اسمی میلگرد")
            if nominal > 100:
                raise ValueError("قطر اسمی میلگرد خارج از محدوده معتبر است")


@exact
def preview_beam(data: dict[str, Any], engine: Any) -> dict[str, Any]:
    """Return individually approved rows and blockers; never invent missing values.

    Preview rows are NOT suitable for final BOQ until `ready` becomes True.
    """
    floor_id, beam_id = _validate_identity(data)
    bars = data.get("bars")
    _validate_bar_shape(bars)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    specialist=data.get('measurement_policy')=='beam_specialist_v1'
    if data.get('measurement_policy') not in (None,'beam_specialist_v1'):errors.append('قرارداد متره تیر ناشناخته است')
    physical_bars=set()
    source = data.get("source", {})
    try:
        _validate_source(source)
        validate_evidence_link(source, beam_id)
        if specialist:
            _text(source.get('plan_ref'),'مرجع پلان تیر');_text(source.get('detail_ref'),'مرجع دیتایل تیر')
    except ValueError as exc:
        errors.append(str(exc))

    src_id = source.get("source_id", "") if isinstance(source, dict) else ""
    base_id = f"beam-detail:{floor_id}:{beam_id}"
    geometry = data.get("geometry", {})
    if not isinstance(geometry, dict):
        geometry = {}
    try:
        _text(geometry.get("approved_by"), "تأییدکننده هندسه")
        _text(geometry.get("source_ref"), "مرجع ابعاد تیر")
        dims = {key: _number(geometry.get(key), key) for key in ("length", "width", "depth")}
        dims["count"] = int(_number(geometry.get("count"), "تعداد تیر", integer=True))
        member_count=dims['count']
        if specialist:
            cover=exact_number(geometry.get('cover_m'),'پوشش صریح بتن')
            if cover<=0 or cover*2>=min(exact_number(geometry['width'],'عرض'),exact_number(geometry['depth'],'ارتفاع')):raise ValueError('پوشش بتن با مقطع تیر سازگار نیست')
            _text(geometry.get('cover_ref'),'مرجع پوشش بتن')
            expected={'length','width','depth','count'}
            if not isinstance(geometry.get('variable_units'),dict) or set(geometry['variable_units'])!=expected:raise ValueError('واحدهای ساختاریافته ابعاد تیر ناقص‌اند')
            if any(normalize_unit(geometry['variable_units'][k])!='m' for k in ('length','width','depth')) or normalize_unit(geometry['variable_units']['count'])!='عدد':raise ValueError('قرارداد ابعاد تیر متر و تعداد عدد است')
        if 'sections' in geometry and not specialist:raise ValueError('مقطع متغیر نیازمند قرارداد تخصصی و نواحی مستند است')
        gross = engine.calculate("building", "beam", description=f"بتن تیر {beam_id}", **dims)
        if specialist:
            dims={k:wire(exact_number(geometry[k],'ابعاد '+k)) for k in ('length','width','depth','count')}
            exact_gross=evaluate('length*width*depth*count',dims,variable_units=geometry['variable_units'],output_unit='m3')
            checked_sections=[]
            if 'sections' in geometry:
                sections=geometry['sections']
                if not isinstance(sections,list) or not sections or len(sections)>128:raise ValueError('نواحی مقطع تیر ناقص یا بیش از حدند')
                previous=exact_number(0,'شروع');ids=set();volumes=[]
                for part in sections:
                    reviewed=component_reviewed
                    reviewed(part)
                    ident=_text(part.get('id'),'شناسه ناحیه مقطع');ref=_text(part.get('source_ref'),'مرجع ناحیه');_text(part.get('approved_by'),'بازبین ناحیه')
                    start=exact_number(part.get('start_m'),'شروع ناحیه',True);end=exact_number(part.get('end_m'),'پایان ناحیه')
                    if ident in ids or start!=previous or end<=start or end>exact_number(geometry['length'],'طول'):raise ValueError('ناحیه مقطع تکراری، دارای فاصله یا هم‌پوشانی است')
                    for k in ('width_m','depth_m'):
                        if exact_number(part.get(k),'بعد ناحیه')<=cover*2:raise ValueError('بعد ناحیه با پوشش سازگار نیست')
                    q=evaluate('(end-start)*width*depth*count',{'end':str(end),'start':str(start),'width':part['width_m'],'depth':part['depth_m'],'count':member_count},variable_units={'end':'m','start':'m','width':'m','depth':'m','count':'عدد'},output_unit='m3')
                    ids.add(ident);previous=end;volumes.append(exact_number(q,'حجم'));checked_sections.append({**deepcopy(part),'volume_m3':q})
                if previous!=exact_number(geometry['length'],'طول'):raise ValueError('ناحیه‌های مقطع کل طول تیر را پوشش نمی‌دهند')
                exact_gross=wire(sum(volumes,exact_number(0,'جمع')))
        if "intersections" in geometry:
            reviewed=component_reviewed
            for item in geometry["intersections"]:reviewed(item)
            net, checked_intersections = net_concrete(gross.quantity, geometry["intersections"])
            deduction = gross.quantity - net
            if "deductions_m3" in geometry and not math.isclose(
                    _number(geometry["deductions_m3"], "کسر هم‌پوشانی بتن", zero=True),
                    deduction, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("جمع کسورات بتن با کسر نهایی ناسازگار است")
        else:
            deduction = _number(geometry.get("deductions_m3"), "کسر هم‌پوشانی بتن", zero=True)
            net = gross.quantity - deduction
            checked_intersections = []
        if member_count>1 or specialist:
            scope=geometry.get('deduction_scope')
            if scope not in ('per_member','total_group'):raise ValueError('دامنه کسورات تیرهای هم‌تیپ باید صریح باشد')
            _text(geometry.get('deduction_scope_ref'),'مرجع دامنه کسورات')
            if scope=='per_member':deduction*=member_count;net=gross.quantity-deduction
        if specialist:
            if 'intersections' in geometry:
                raw_ded=sum((exact_number(x['volume_m3'],'کسر') for x in geometry['intersections']),exact_number(0,'جمع'))
            else:raw_ded=exact_number(geometry.get('deductions_m3'),'کسورات',True)
            deduction=wire(raw_ded*(member_count if geometry['deduction_scope']=='per_member' else 1))
            net=evaluate('gross-deduction',{'gross':exact_gross,'deduction':deduction},variable_units={'gross':'m3','deduction':'m3'},output_unit='m3')
        if not math.isfinite(float(net)) or exact_number(net,'خالص',True) <= 0:
            raise ValueError("کسر هم‌پوشانی، حجم خالص بتن تیر را نامعتبر می‌کند")
        rows.append({"source_id": base_id+":concrete", "code": "beam", "domain": "building",
                     "description": f"بتن خالص تیر {beam_id}", "quantity": net, "unit": "m3",
                     "formula": f"{gross.formula if not specialist or not checked_sections else 'جمع حجم ناحیه‌های مقطع مستند'} − کسر هم‌پوشانی مستند {deduction} m³",
                     "params": {**dims, "deductions_m3": deduction, "intersections": checked_intersections,**({"gross_m3":exact_gross,"sections":checked_sections,"variable_units":geometry["variable_units"],"deduction_scope":geometry["deduction_scope"]} if specialist else {})}})
    except (ValueError, TypeError, KeyError) as exc:
        errors.append("بتن تیر: " + str(exc))

    formwork = data.get("formwork", {})
    if not isinstance(formwork, dict):
        formwork = {}
    try:
        _text(formwork.get("approved_by"), "تأییدکننده قالب‌بندی")
        _text(formwork.get("source_ref"), "مرجع سطوح در تماس با قالب")
        if "surfaces" in formwork:
            reviewed=component_reviewed
            faces=[];gross_faces=[]
            for raw in formwork['surfaces']:
                reviewed(raw)
                if 'gross_area_m2' not in raw:faces.append(raw);continue
                if raw.get('role') not in ('bottom_face','side1','side2','end','other'):raise ValueError('نقش سطح قالب نامعتبر است')
                if type(raw.get('contact')) is not bool:raise ValueError('تماس سطح با قالب باید صریح باشد')
                gross_area=exact_number(raw['gross_area_m2'],'سطح ناخالص')
                deductions=raw.get('deductions',[]);seen=set();ded=exact_number(0,'کسر')
                for v in deductions:
                    reviewed(v);sid=_text(v.get('id'),'شناسه کسر سطح');_text(v.get('source_ref'),'مرجع کسر سطح')
                    if sid in seen:raise ValueError('کسر سطح تکراری است')
                    seen.add(sid);ded+=exact_number(v.get('area_m2'),'مساحت کسر')
                net_area=gross_area-ded
                if gross_area<=0 or net_area<0:raise ValueError('مساحت سطح یا کسورات نامعتبر است')
                _text(raw.get('approved_by'),'بازبین سطح');_text(raw.get('source_ref'),'مرجع سطح')
                gross_faces.append(gross_area)
                if raw['contact'] and net_area>0:faces.append({**raw,'net_area_m2':wire(net_area)})
            if not faces:raise ValueError('سطح مثبت در تماس با قالب موجود نیست؛ عدم کاربرد نیازمند قرارداد مستقل است')
            area, verified_faces = net_formwork({**formwork,'surfaces':faces})
            if "net_area_m2" in formwork and not math.isclose(
                    _number(formwork["net_area_m2"], "مساحت خالص قالب‌بندی"), area,
                    rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("جمع سطوح قالب با مقدار نهایی تعارض دارد")
        else:
            area = _number(formwork.get("net_area_m2"), "مساحت خالص قالب‌بندی")
            verified_faces = []
        repeat=int(_number(geometry.get('count'),'تعداد تیر',integer=True))
        scope=formwork.get('area_scope')
        if repeat>1 or specialist:
            if scope not in ('per_member','total_group'):raise ValueError('دامنه مساحت قالب تیرهای هم‌تیپ باید صریح باشد')
            _text(formwork.get('area_scope_ref'),'مرجع دامنه مساحت قالب')
            if scope=='per_member':area*=repeat
        if specialist:
            raw_area=sum((exact_number(face['net_area_m2'],'سطح') for face in faces),exact_number(0,'جمع')) if 'surfaces' in formwork else exact_number(formwork['net_area_m2'],'سطح')
            area=evaluate('area*repeat',{'area':str(raw_area),'repeat':repeat if scope=='per_member' else 1},variable_units={'area':'m2','repeat':'عدد'},output_unit='m2')
        rows.append({"source_id": base_id+":formwork", "code": "formwork", "domain": "building",
                     "description": f"قالب‌بندی تیر {beam_id}", "quantity": area, "unit": "m2",
                     "formula": "سطوح واقعی و تأییدشده در تماس با قالب", "params": {"net_area_m2": area, "surfaces": deepcopy(formwork.get("surfaces",verified_faces)),"gross_area_m2":wire(sum(gross_faces,exact_number(0,"جمع"))*(repeat if scope=="per_member" else 1)) if "surfaces" in formwork and gross_faces else None,"area_scope":scope,"member_count":repeat}})
    except (ValueError, TypeError) as exc:
        errors.append("قالب‌بندی: " + str(exc))

    for kind in BAR_TYPES:
        bar = bars[kind]
        state = bar["status"]
        if state == "not_applicable":
            try:
                _text(bar.get("approved_by"), "تأییدکننده عدم کاربرد")
                _text(bar.get("reason"), "دلیل عدم کاربرد")
                _text(bar.get("source_ref"), "مرجع بررسی دیتایل")
            except ValueError as exc:
                errors.append(f"{BAR_LABELS[kind]}: {exc}")
        elif state == "confirmed":
            try:
                _text(bar.get("approved_by"), "تأییدکننده میلگرد")
                _text(bar.get("source_ref"), "مرجع دیتایل میلگرد")
                # Explicit segments support variable stirrup zones and differing bar sizes.
                # Cut length includes reviewed hooks, laps and bends; never infer it from span.
                repeat=int(_number(geometry.get('count'),'تعداد تیر',integer=True));scope=bar.get('count_scope')
                if repeat>1 or specialist:
                    if scope not in ('per_member','total_group'):raise ValueError('دامنه تعداد میلگرد تیرهای هم‌تیپ باید صریح باشد')
                    _text(bar.get('count_scope_ref'),'مرجع دامنه تعداد میلگرد')
                if specialist and kind=='stirrups' and 'segments' not in bar:raise ValueError('خاموت تخصصی نیازمند جانمایی و تعداد واقعی ناحیه‌ها است')
                if specialist and repeat>1 and kind=='stirrups' and scope!='per_member':raise ValueError('جانمایی خاموت تکراری باید برای یک عضو با تکرار صریح باشد')
                raw_segments=bar.get('segments',[bar])
                if not isinstance(raw_segments,list) or not raw_segments:raise ValueError('بازه‌های میلگرد ناقص‌اند')
                if len({json.dumps(x,sort_keys=True,ensure_ascii=False) for x in raw_segments})!=len(raw_segments):raise ValueError('بازه میلگرد عیناً تکرار شده است')
                if specialist:
                    for segment in raw_segments:
                        reviewed=component_reviewed
                        reviewed(segment)
                        for piece in segment.get('length_parts_m',[]):reviewed(piece)
                        ident=_text(segment.get('id'),'شناسه مستقل میلگرد')
                        if ident in physical_bars:raise ValueError('شناسه میلگرد فیزیکی در گروه‌ها تکرار شده است')
                        physical_bars.add(ident)
                        diameter=_number(segment.get('nominal_diameter_mm'),'قطر مستند')
                        if diameter>100:raise ValueError('قطر خارج از قرارداد معتبر است')
                        _text(segment.get('cut_length_ref'),'مرجع طول برش محور شامل خم، قلاب و مهار')
                        if 'length_parts_m' in segment and 'cut_length_m' in segment:raise ValueError('روش طول برش مبهم است؛ تنها یکی از طول مستقیم تأییدشده یا اجزای طول مجاز است')
                        if kind=='stirrups':
                            _text(segment.get('shape_ref'),'مرجع شکل خاموت');_text(segment.get('section_ref'),'مرجع ابعاد خاموت')
                            if segment.get('shape_kind')!='rectangular':raise ValueError('شکل خاموت خارج از قرارداد این نوبت است')
                            for field,limit in [('section_width_m',geometry['width']),('section_depth_m',geometry['depth'])]:
                                size=exact_number(segment.get(field),'بعد واقعی خاموت')
                                if size<=0 or size>exact_number(limit,'بعد تیر')-2*exact_number(geometry['cover_m'],'پوشش'):raise ValueError('ابعاد بیرونی خاموت با پوشش و مقطع تیر ناسازگار است')
                            distance=evaluate('last-first',{'last':segment.get('last_bar_m'),'first':segment.get('first_bar_m')},variable_units={'last':'m','first':'m'},output_unit='m')
                            travel=evaluate('(count-1)*spacing',{'count':segment.get('count'),'spacing':segment.get('spacing_m')},variable_units={'count':'عدد','spacing':'m'},output_unit='m')
                            if exact_number(distance,'فاصله')!=exact_number(travel,'جانمایی'):raise ValueError('تعداد و جانمایی واقعی خاموت با فاصله صریح ناسازگار است')
                        else:
                            position=_text(segment.get('position'),'موقعیت مستقل میلگرد')
                            if position not in ('top','bottom','span','support','side','crosstie'):raise ValueError('موقعیت میلگرد نامعتبر است')
                segments = raw_segments
                if kind == "stirrups" and "segments" in bar:
                    # A partial or overlapping zone schedule must never enter BOQ.
                    segments = validate_stirrup_zones(segments, geometry.get("length"))
                if not isinstance(segments, list) or not segments:
                    raise ValueError("بازه‌های میلگرد باید فهرست غیرخالی باشند")
                quantities = []
                validated = []
                for segment in segments:
                    if not isinstance(segment, dict):
                        raise ValueError("دیتایل هر بازه میلگرد باید ساختار معتبر داشته باشد")
                    _text(segment.get("source_ref"), "مرجع بازه میلگرد")
                    count = int(_number(segment.get("count"), "تعداد میلگرد", integer=True))
                    unit_weight_source = _text(segment.get("unit_weight_source"), "منبع وزن واحد")
                    if "length_parts_m" in segment:
                        reviewed_segment = dict(segment)
                        reviewed_segment.setdefault("approved_by", bar["approved_by"])
                        cut, cut_metadata = reviewed_cut_length(reviewed_segment)
                    else:
                        cut = _number(segment.get("cut_length_m"), "طول برش تأییدشده")
                        cut_metadata = {"method": "approved_cut_length", "cut_length_m": cut,
                                        "source_ref": segment["source_ref"]}
                    weight = _number(segment.get("unit_weight_kg_m"), "وزن واحد تأییدشده")
                    result = engine.calculate("building", "rebar", description=BAR_LABELS[kind],
                                              count=count, length=cut, unit_weight=weight)
                    quantities.append(result.quantity)
                    segment_parameters = {"count": count, "length": cut, "unit_weight": weight,
                                          "source_ref": segment["source_ref"], "cut": cut_metadata}
                    segment_parameters["unit_weight_source"] = unit_weight_source
                    if kind == "stirrups" and "segments" in bar:
                        segment_parameters.update({field: segment[field] for field in (
                            "name", "start_m", "end_m", "spacing_m", "first_bar_m", "last_bar_m")})
                    validated.append(segment_parameters)
                total = math.fsum(quantities)
                if repeat>1 and scope=='per_member':total*=repeat
                if specialist:
                    weights=[]
                    for raw,checked in zip(raw_segments,validated):
                        cut=evaluate('+'.join('p'+str(i) for i in range(len(raw['length_parts_m']))),{'p'+str(i):part['length_m'] for i,part in enumerate(raw['length_parts_m'])},variable_units={'p'+str(i):'m' for i in range(len(raw['length_parts_m']))},output_unit='m') if 'length_parts_m' in raw else raw['cut_length_m']
                        q=evaluate('count*cut*weight*repeat',{'count':raw['count'],'cut':cut,'weight':raw['unit_weight_kg_m'],'repeat':repeat if scope=='per_member' else 1},variable_units={'count':'عدد','cut':'m','weight':'kg/m','repeat':'عدد'},output_unit='kg')
                        weights.append(exact_number(q,'وزن'));checked['cut']={**deepcopy(checked['cut']),'cut_length_m':cut,'length_parts_m':deepcopy(raw.get('length_parts_m',[]))};checked.update(id=raw['id'],nominal_diameter_mm=raw['nominal_diameter_mm'],position=raw.get('position','stirrup'),length=cut,unit_weight=raw['unit_weight_kg_m'],variable_units={'count':'عدد','length':'m','unit_weight':'kg/m'},cut_length_ref=raw['cut_length_ref'],**{k:raw[k] for k in ('shape_kind','shape_ref','section_width_m','section_depth_m','section_ref') if k in raw})
                    total=wire(sum(weights,exact_number(0,'جمع')))

                if exact_number(total,'وزن کل',True) <= 0:
                    raise ValueError("مجموع وزن میلگرد معتبر نیست")
                rows.append({"source_id": base_id+":"+kind, "code": "rebar", "domain": "building",
                             "description": f"{BAR_LABELS[kind]} تیر {beam_id}", "quantity": total,
                             "unit": "kg", "formula": "جمع (تعداد × طول برش × وزن واحد) بازه‌های تأییدشده",
                             "params": {"segments": validated,"count_scope":scope,"member_count":repeat}})
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"{BAR_LABELS[kind]}: {exc}")
        else:
            errors.append(f"{BAR_LABELS[kind]}: هنوز {state} است")

    if not rows:
        errors.append("هیچ کمیت تأییدشده‌ای قابل پیش‌نمایش نیست")
    return {"floor_id": floor_id, "beam_id": beam_id, "source_id": src_id,
            "ready": not errors, "blockers": errors, "preview_only": True, "rows": rows}


class BeamDetailWorkflow:
    """SQLite-backed beam detail lifecycle reusing canonical store and BOQ engine."""

    def __init__(self, store: Any, engine: Any):
        self.store, self.engine = store, engine

    def _project(self, project_id: str) -> tuple[dict[str, Any], str]:
        digest = self.store.current_digest(project_id)
        # Existing ProjectStore caches payloads; invalidate before an optimistic write.
        if hasattr(self.store, "_cache"):
            self.store._cache.pop(project_id, None)
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return project, digest

    def get(self, project_id: str, floor_id: str, beam_id: str) -> dict[str, Any] | None:
        self.store._cache.pop(project_id,None)
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        key = _beam_key(_text(floor_id, "طبقه"), _text(beam_id, "شناسه تیر"))
        record = (project.get(REGISTER) or {}).get(key)
        from core.takeoff.manual_formula_amendments import beam_current
        return beam_current(project,key) if record else None

    def save_draft(self, project_id: str, draft: dict[str, Any], *, expected_revision: int = 0, reason: str = "ثبت پیش‌نویس") -> dict[str, Any]:
        floor_id, beam_id = _validate_identity(draft)
        _validate_bar_shape(draft.get("bars"))
        # Reject malformed source at the time it is supplied; an empty source is okay for a draft.
        if draft.get("source"):
            _validate_source(draft["source"])
            validate_evidence_link(draft["source"], beam_id)
        try:
            json.dumps(draft, allow_nan=False, ensure_ascii=False)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("داده غیرمتناهی یا غیرقابل ذخیره در فرم تیر وجود دارد") from exc
        project, digest = self._project(project_id)
        register = project.setdefault(REGISTER, {})
        if not isinstance(register, dict):
            raise ValueError("ساختار دفتر متره تیر معتبر نیست")
        key = _beam_key(floor_id, beam_id)
        previous = register.get(key)
        if previous and previous["data"].get("measurement_policy")=="beam_specialist_v1" and draft.get("measurement_policy")!="beam_specialist_v1":raise ValueError("حذف قرارداد تخصصی تیر مجاز نیست")
        if previous and previous.get("status") == "committed":
            raise ValueError("تیر به ریزمتره منتقل شده؛ تغییر آن نیازمند فرایند اصلاح نسخه است")
        revision = previous.get("revision", 0) if previous else 0
        if expected_revision != revision:
            raise RuntimeError("تعارض نسخه متره تیر؛ اطلاعات را دوباره بارگذاری کنید")
        source = draft.get("source", {})
        if previous and previous["data"].get("source") != source:
            if any(x["status"] in {"confirmed", "not_applicable"} for x in draft["bars"].values()):
                raise ValueError("منبع نقشه تغییر کرده؛ ابتدا تأیید اقلام میلگرد را بازنشانی کنید")
        if source and source.get("source_id"):
            require_source_unused(project, source["source_id"], exclude=(REGISTER, key))
        from core.takeoff.manual_formula_amendments import digest as payload_digest
        proposal=deepcopy(draft);review=proposal.pop('component_review',None)
        fresh=isinstance(review,dict) and review.get('base_revision')==revision and review.get('reviewer') and review.get('digest')==payload_digest(proposal)
        if fresh:
            report=preview_beam(proposal,self.engine)
            if not report['ready']:raise ValueError('بازبینی نسخه ناقص معتبر نیست')
        else:require_reset_of_changed_approvals(previous['data'] if previous else None,draft)
        if previous:project.setdefault('beam_detail_history',[]).append({'beam_key':key,'revision':revision+1,'reason':_text(reason,'علت اصلاح'),'previous':deepcopy(previous),'at':datetime.now(timezone.utc).isoformat()})
        payload = deepcopy(draft)
        entry = {"status": "draft", "revision": revision + 1, "data": payload,
                 "updated_at": datetime.now(timezone.utc).isoformat()}
        register[key] = entry
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(entry)

    def preview(self, project_id: str, floor_id: str, beam_id: str) -> dict[str, Any]:
        entry = self.get(project_id, floor_id, beam_id)
        if entry is None:
            raise KeyError(beam_id)
        result = preview_beam(entry["data"], self.engine)
        result["revision"] = entry["revision"]
        result["committed"] = entry["status"] == "committed"
        return result

    def commit(self, project_id: str, floor_id: str, beam_id: str, *, expected_revision: int) -> dict[str, Any]:
        project, digest = self._project(project_id)
        key = _beam_key(_text(floor_id, "طبقه"), _text(beam_id, "شناسه تیر"))
        entry = (project.get(REGISTER) or {}).get(key)
        if not entry:
            raise KeyError(beam_id)
        if entry["status"] == "committed":
            raise ValueError("این تیر قبلاً به ریزمتره منتقل شده است")
        if entry["revision"] != expected_revision:
            raise RuntimeError("تعارض نسخه متره تیر؛ ثبت نهایی رد شد")
        report = preview_beam(entry["data"], self.engine)
        if not report["ready"]:
            raise ValueError("متره ناقص است؛ انتقال به ریزمتره ممنوع: " + "؛ ".join(report["blockers"]))
        data = entry["data"]
        source = data["source"]
        prior = project.get("takeoffs", [])
        new_ids = {x["source_id"] for x in report["rows"]}
        new_takeoffs = deepcopy(prior)
        for row in report["rows"]:
            new_takeoffs.append({
                "id": f"beam-detail:{key}:{row['code']}:{row['source_id'].rsplit(':', 1)[-1]}",
                "member_code": beam_id, "source_id": row["source_id"], "domain": row["domain"],
                "item": row["code"], "params": row["params"], "revision": entry["revision"],
                "description": row["description"], "system": floor_id,
                "provenance": deepcopy(source),
                "quantities": [{"code": row["code"], "title": row["description"],
                                "system": floor_id, "unit": row["unit"], "amount": row["quantity"],
                                "formula": row["formula"], "warning": "",
                                "price_code": None, "unit_price": None}],
            })
        validated = validate_commit_rows(
            project, new_takeoffs[len(prior):], source_id=source["source_id"],
            expected_current_registry=(REGISTER, key))
        project["takeoffs"], project["boq"] = rebuild_project_boq(
            project, list(prior) + validated)
        entry["status"] = "committed"
        entry["committed_at"] = datetime.now(timezone.utc).isoformat()
        entry["committed_source_ids"] = sorted(new_ids)
        self.store.save(project_id, project, expected_digest=digest)
        return {"status": "committed", "takeoff_rows": len(report["rows"]),
                "revision": entry["revision"], "source_ids": sorted(new_ids)}
