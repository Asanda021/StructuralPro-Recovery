"""Read-only handoff adapter for documented RC bored piles and existing BOQ.

Does not register, save, approve, commit, infer excavation or clear cap overlap.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, Context, localcontext

from core.takeoff.bored_pile_specialist_chat import compile_piles, ident
from core.takeoff.commit_guards import require_source_unused, validate_commit_rows

POLICY = "bored_pile_aec_bridge_chat_v1"
CODES = {"concrete_net":"bored_pile_concrete", "formwork":"bored_pile_formwork",
         "rebar_longitudinal":"bored_pile_rebar_longitudinal",
         "rebar_spiral_ties":"bored_pile_rebar_spiral_ties",
         "rebar_crossties":"bored_pile_rebar_crossties",
         "rebar_starters":"bored_pile_rebar_starters"}


class PileBridgeError(ValueError):
    pass


def _old_claims(project, data):
    if not isinstance(project, dict) or not isinstance(project.get("id"),str) or project["id"] != data["project_id"]:
        raise PileBridgeError("شناسه پروژه مبنا با دیتایل شمع مغایرت دارد")
    kinds = ("bored_pile", "pile_foundation", "pile_cap")
    pile_ids={p["id"] for p in data["piles"]}
    physical_ids={p["physical_id"] for p in data["piles"]}
    for registry in ("reviewed_structural_members", "reviewed_aec_systems", "beam_detail_register"):
        records = project.get(registry) or {}
        if not isinstance(records,dict):
            raise PileBridgeError("دفتر ثبت دارای ساختار نامعتبر است")
        for record in records.values():
            if not isinstance(record,dict) or not isinstance(record.get("data"),dict):
                raise PileBridgeError("عضو ثبت‌شده فاقد ساختار معتبر است")
            old=record["data"]
            if old.get("kind") not in kinds:
                continue
            if old.get("kind") in ("bored_pile", "pile_foundation") and old.get("floor_id")==data["floor_id"]:
                if old.get("member_id") in pile_ids or old.get("system_id") in pile_ids:
                    raise PileBridgeError("شمع قبلاً در مسیر عمومی ثبت شده؛ مهاجرت خاموش ممنوع است")
                g=old.get("geometry") or {}
                if isinstance(g,dict) and (g.get("physical_pile_id") in physical_ids or g.get("physical_id") in physical_ids):
                    raise PileBridgeError("هویت شمع قبلاً ثبت شده است")
    for row in project.get("takeoffs") or []:
        if not isinstance(row,dict) or ("params" in row and not isinstance(row["params"],dict)):
            raise PileBridgeError("ساختار برداشت ذخیره‌شده معتبر نیست")
        p=row.get("params") or {}
        if p.get("physical_pile_id") in physical_ids:
            raise PileBridgeError("شمع قبلاً به متره منتقل شده است")
        if set(p.get("claimed_piles") or []) & physical_ids:
            raise PileBridgeError("هویت شمع با برداشت قبلی تداخل دارد")
    require_source_unused(project,data["source"]["source_id"])


def compile_preview(data, project, *, independent_reviewer, ownership_reference):
    engine=compile_piles(data)
    _old_claims(project,data)
    reviewer=ident(independent_reviewer,"بازبین مستقل")
    ref=ident(ownership_reference,"مرجع کنترل مالکیت")
    approvals=[]
    def collect(x):
        if isinstance(x,dict):
            if isinstance(x.get("approved_by"),str):
                approvals.append(x["approved_by"])
            for v in x.values():collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    collect(data)
    if reviewer.casefold() in {s.casefold() for s in approvals}:
        raise PileBridgeError("بازبین مستقل نباید تأییدکننده دیتایل‌ها باشد")
    floor=data["floor_id"]; group=data["group_id"]
    ready=[];candidates=[]
    for row in engine["rows"]:
        code=CODES[row["kind"]]
        sid=f"aec:bored_pile:{floor}:{group}:{row['pile_id']}:{row['physical_id']}:{row['kind']}"
        pile_physical=next(p["physical_id"] for p in data["piles"] if p["id"] == row["pile_id"])
        params={"bridge_policy":POLICY,"physical_pile_id":pile_physical,
                "component_physical_id":row["physical_id"],"source_input_sha256":engine["source_sha256"],
                "pile_claims":engine["physical_claims"],"source_refs":row["source_refs"],
                "ownership_ref":ref,"axis_ref":data["datum"]["axis_ref"],
                "vertical_datum_ref":data["datum"]["vertical_datum_ref"]}
        if row["kind"]=="concrete_net":
            params["gross_concrete_m3"]=row["evidence"]["gross_m3"]
            params["intersections"]=[{"id":"bored-pile:"+pile_physical+":"+cut["id"],
                                      "source_ref":cut["source_ref"],"volume_m3":cut["volume_m3"]}
                                     for cut in row["evidence"]["deductions"]]
        preview={"source_id":sid,"item_code":code,"quantity":row["quantity"],"unit":row["unit"],
                 "formula":row["formula"],"role":"work","component_physical_id":row["physical_id"]}
        ready.append(preview)
        candidates.append({"id":sid,"source_id":sid,"member_code":row["pile_id"],
                           "domain":"building","item":code,"system":floor,
                           "description":"متره مستند شمع درجا "+row["pile_id"]+" ـ "+row["kind"],
                           "params":deepcopy(params),"provenance":deepcopy(data["source"]),
                           "review":{"approved_by":reviewer,"component":row["kind"],
                                     "method":POLICY,"measurement_source":row["source_refs"][0],
                                     "review_reference":ref},
                           "quantities":[{"code":code,"title":"متره مستند شمع درجا "+row["kind"],
                                          "system":floor,"unit":row["unit"],"amount":row["quantity"],
                                          "formula":row["formula"],"role":"work","price_code":None,"unit_price":None}]})
    # Guard row formats, known duplicate sources, deductions and manual mapping.
    validate_commit_rows(project,candidates,source_id=data["source"]["source_id"])
    with localcontext(Context(prec=256)):
        unit_totals={unit:str(sum((Decimal(r["quantity"]) for r in ready if r["unit"]==unit),Decimal(0))) for unit in ("m3","m2","kg")}
    if any(Decimal(unit_totals[k]) != Decimal(engine["totals"][k]) for k in unit_totals):
        raise PileBridgeError("جمع موتور و پل ناسازگار است")
    return {"policy":POLICY,"status":"preview_only_not_integrated","commit_allowed":False,
            "blockers":["نیازمند تطبیق مستقل هویت و مالکیت بتن/میلگرد بین شمع، کلاهک، ستون و سازه",
                        "نیازمند اتصال رسمی فرم، SQLite، CAS، بازبینی، اصلاحیه و گزارش مشترک"],
            "input_sha256":engine["source_sha256"],"totals":engine["totals"],
            "physical_claims":deepcopy(engine["physical_claims"]),
            "preview_rows":ready,"takeoff_candidates":candidates}
