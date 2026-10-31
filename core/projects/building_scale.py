"""Reviewed floor scaling for WBS quantity forecasts.

Only a source explicitly marked as ONE typical repeated floor may be
scaled by the selected repeat count. A whole-building plan must NEVER be
multiplied again. Foundation, excavation, roof, façade and site are excluded.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal,InvalidOperation

REPEATABLE={
"block_wall","brick_wall","aac_wall","plaster_base","finish_plaster",
"floor_screed","floor_tile","wall_tile","stone_floor","paint_primer",
"paint_finish","door_install","ceiling_gypsum","plumbing_water",
"sewage_pipe","gas_pipe","radiator","hvac_pipe","hvac_duct",
"hvac_unit","conduit","wiring","switch_socket","lighting",
"data_network","sanitary","cable_tray","panel_board",
"column_rebar","column_form","column_concrete","beam_rebar",
"slab_form","slab_rebar","slab_concrete",
}
def building_scope(floors,typical_area_m2,*,source_scope="whole_building",
                   repeat_floors=1):
    if type(floors) is not int or not 1<=floors<=200:
        raise ValueError("تعداد کل طبقات باید عدد صحیح معتبر باشد")
    if type(repeat_floors) is not int or not 1<=repeat_floors<=floors:
        raise ValueError("طبقات همسان باید بین ۱ و تعداد کل طبقات باشند")
    if source_scope not in ("whole_building","single_typical_floor"):
        raise ValueError("دامنه نقشه باید کل ساختمان یا یک طبقه تیپ باشد")
    if source_scope=="whole_building" and repeat_floors!=1:
        raise ValueError("نقشه کل ساختمان نباید مجدداً در طبقات ضرب شود")
    if isinstance(typical_area_m2,bool):raise ValueError("متراژ معتبر نیست")
    try: area=Decimal(str(typical_area_m2))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise ValueError("متراژ طبقه نامعتبر است") from exc
    if not area.is_finite() or area<0 or area>1000000:
        raise ValueError("متراژ غیرمعمول یا نامعتبر است")
    return {
        "total_floors":floors,
        "typical_floor_area_m2":str(area),
        "source_scope":source_scope,
        "repeat_floors":repeat_floors,
        "gross_area_proxy_m2":str(area*floors) if area>0 else None,
        "scope_review":"USER_CONFIRMED_REPEAT" if source_scope=="single_typical_floor"
                        else "AS_DRAWN_WHOLE_BUILDING",
        "warning":"متراژ به تنهایی مقدار دیوار، بتن و لوله را تعیین نمی‌کند؛ "
                  "برای مدت واقعی باید متره و تعداد اکیپ معتبر موجود باشد",
    }

def set_building_scope(plan,profile):
    from core.drawings.workflow_planning import recompute_schedule
    p=deepcopy(plan)
    p["building_scope"]=deepcopy(profile)
    return recompute_schedule(p)

def effective_quantity(task_code,raw_quantity,building):
    """Returns (quantity, provenance) without changing source takeoff rows."""
    q=Decimal(str(raw_quantity))
    if not q.is_finite() or q<0:
        raise ValueError("مقدار متره برای برنامه زمانی معتبر نیست")
    if (building.get("source_scope")=="single_typical_floor"
            and task_code in REPEATABLE):
        repeat=building["repeat_floors"]
        return q*repeat,{"factor":repeat,
              "meaning":"TYPICAL_FLOOR_USER_CONFIRMED",
              "base_quantity":str(q)}
    return q,{"factor":1,"meaning":"AS_DRAWN","base_quantity":str(q)}

def duration_comparison(per_floor_quantity,task_code,unit,*,floor_counts=(5,6),
                        crews=None,efficiency="1"):
    from core.projects.production_catalog import productivity_days,CATALOG
    if task_code not in REPEATABLE or task_code not in CATALOG:
        raise ValueError("فعالیت برای محاسبه طبقه تیپ معتبر نیست")
    results=[]
    for floors in floor_counts:
        if type(floors) is not int or not 1<=floors<=200:
            raise ValueError("تعداد طبقه نامعتبر است")
        q=Decimal(str(per_floor_quantity))*floors
        model=productivity_days(task_code,q,unit,crews=crews,efficiency=efficiency)
        results.append({"floors":floors,"total_quantity":str(q),
                        **model,"status":"DRAFT_FROM_USER_CONFIRMED_TYPICAL_FLOOR"})
    return results
