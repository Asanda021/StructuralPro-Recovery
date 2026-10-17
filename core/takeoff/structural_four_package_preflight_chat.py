"""Read-only combined preflight for four independent StructuralPro Chat packages.

NEVER writes SQLite, grants financial approval, or replaces signed cross-member
ownership evidence. Rows are only synthetic candidates until Work integrates
source, identity, amendment and financial review in the actual project ledger.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal, Context, Inexact, Rounded, localcontext
from core.takeoff.commit_guards import validate_commit_rows, rebuild_project_boq

EXPECTED = ("shear_wall", "stair", "bored_pile")
POLICIES = {
    "shear_wall": "shear_wall_aec_bridge_chat_v1",
    "stair": "stair_bridge_chat_preflight_v1",
    "bored_pile": "bored_pile_aec_bridge_chat_v1",
}

class CombinedPreflightError(ValueError):
    pass


def audit(previews: dict, source_ids: dict, ownership: dict, project: dict) -> dict:
    """Check source/row identities and mixed BOQ dry-run; explicitly block commit.

    ``ownership`` is the OUTPUT of the independent rebar ownership reconciliation,
    NOT an authorization to pay: legacy rows and bar-to-adapter mapping remain open.
    Inputs and ProjectStore snapshots are never mutated.
    """
    if not all(isinstance(x, dict) for x in (previews, source_ids, ownership, project)):
        raise CombinedPreflightError("اسناد ورودی و Snapshot باید معتبر باشند")
    if set(previews) != set(EXPECTED) or set(source_ids) != set(EXPECTED):
        raise CombinedPreflightError("سه موتور سازه‌ای و شناسه منابع آن‌ها الزامی‌اند")
    if not isinstance(project.get("id"), str) or not project["id"].strip():
        raise CombinedPreflightError("هویت Snapshot اصلی الزامی است")
    if ownership.get("project_id") != project["id"] or ownership.get("commit_allowed") is not False:
        raise CombinedPreflightError("دفتر میلگرد متعلق به این پروژه یا از نوع پیش‌نمایش نیست")
    if ownership.get("policy") != "shared_rebar_ownership_chat_v1":
        raise CombinedPreflightError("قرارداد دفتر میلگرد ناشناخته است")
    if not isinstance(ownership.get("physical_bar_paid_once"), list):
        raise CombinedPreflightError("فهرست مالکیت میلگرد نامعتبر است")
    if any(not isinstance(s, str) or not s or s.strip()!=s for s in source_ids.values()):
        raise CombinedPreflightError("شناسه منبع معتبر، یکتا و بدون فاصله اضافی لازم است")
    if len(set(source_ids.values())) != len(EXPECTED):
        raise CombinedPreflightError("دو موتور، شناسه برداشت مشترک اعلام کرده‌اند")

    rows=[]; seen=set(); physical_ops=set(); quantities={}; unlinked=[]
    for kind in EXPECTED:
        preview=previews[kind]
        if not isinstance(preview, dict) or preview.get("policy") != POLICIES[kind]:
            raise CombinedPreflightError("قرارداد تخصصی موتور تغییر کرده است")
        if preview.get("status") != "preview_only_not_integrated" or preview.get("commit_allowed") is not False:
            raise CombinedPreflightError("پیش‌نمایش نباید حق ثبت قطعی داشته باشد")
        candidates=preview.get("takeoff_candidates")
        if not isinstance(candidates, list) or not candidates:
            raise CombinedPreflightError("ردیف‌های موتور ناقص‌اند")
        validate_commit_rows(project, candidates, source_id=source_ids[kind])
        for row in candidates:
            if not isinstance(row, dict) or not isinstance(row.get("params"), dict):
                raise CombinedPreflightError("ردیف متره یا هویت قطعه نامعتبر است")
            sid=row.get("source_id")
            if not isinstance(sid,str) or not sid.strip() or sid.strip()!=sid or row.get("id")!=sid or sid in seen:
                raise CombinedPreflightError("شناسه متره مشترک، تکراری یا ناسازگار است")
            seen.add(sid)
            provenance=row.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("source_id") != source_ids[kind]:
                raise CombinedPreflightError("ردیف به منبع اصلی موتور متصل نیست")
            q=row.get("quantities")
            if not isinstance(q,list) or len(q)!=1 or not isinstance(q[0],dict):
                raise CombinedPreflightError("ریزکمیت خارج از قرارداد تک‌ردیفی این Adapter است")
            unit=q[0].get("unit")
            if unit not in ("m3","m2","kg"):
                raise CombinedPreflightError("واحد ناشناخته در بسته مشترک")
            raw=q[0].get("amount")
            if isinstance(raw,(bool,float)) or not isinstance(raw,(str,int,Decimal)):
                raise CombinedPreflightError("مقدار باید Decimal دقیق یا رشته دهدهی باشد")
            try: amount=Decimal(raw)
            except Exception as exc: raise CombinedPreflightError("مقدار عددی ناسازگار") from exc
            if not amount.is_finite() or amount<=0:
                raise CombinedPreflightError("ردیف غیرمثبت یا نامتناهی")
            quantities.setdefault(unit,[]).append(amount)
            params=row["params"]
            physical=params.get("physical_component_id") or params.get("component_physical_id")
            if physical is not None:
                if not isinstance(physical,str) or not physical.strip():
                    raise CombinedPreflightError("شناسه فیزیکی قطعه نامعتبر است")
                operation=q[0].get("code")
                identity=(physical,operation)
                if identity in physical_ops:
                    raise CombinedPreflightError("یک قطعه فیزیکی و عملیات در دو موتور مشترک است")
                physical_ops.add(identity)
            if unit=="kg":
                unlinked.append({"source_id":sid,"component":kind,
                                 "physical_component_id":physical,
                                 "physical_bar_id":params.get("physical_bar_id")})
            rows.append(deepcopy(row))
    # Validates the entire union, including cross-package deductions and row IDs.
    validate_commit_rows(project, rows, source_id=source_ids[EXPECTED[0]])
    _,boq=rebuild_project_boq(project,list(project.get("takeoffs") or [])+rows)
    with localcontext(Context(prec=1024)) as ctx:
        ctx.traps[Inexact]=True
        ctx.traps[Rounded]=True
        totals={k:format(sum(v,Decimal(0)),"f") for k,v in sorted(quantities.items())}

    paid=ownership["physical_bar_paid_once"]
    bar_ids={r.get("physical_bar_id") for r in paid if isinstance(r,dict)}
    missing_bar_link=sorted(r["source_id"] for r in unlinked if not isinstance(r["physical_bar_id"],str) or r["physical_bar_id"] not in bar_ids)
    blockers=[
        "ثبت قطعی مسدود: سه موتور هنوز گردش SQLite/CAS، بازبینی و اصلاحیه اصلی را ندارند",
        "مالکیت مشترک بتن، قالب و سطح تماس بین اعضا با نقشه/مدرک واقعی تطبیق نشده است",
        "دفتر مالکیت میلگرد به‌جای ادغام واقعی، فقط پیش‌نمایش دارای مانع است",
        "قرارداد صریح تطبیق ریزردیف‌های kg با physical_bar_id، تعداد و طول/جرم مالک پرداخت لازم است",
        "داده نمونه مصنوعی، تأیید سازه یا BOQ قابل پرداخت نیست",
    ]
    if missing_bar_link:
        blockers.append("ردیف‌های kg فاقد نگاشت اثبات‌شده به میلگرد دفتر مالکیت: "+str(len(missing_bar_link)))
    owner_blockers=ownership.get("blockers")
    if not isinstance(owner_blockers,list) or not owner_blockers:
        raise CombinedPreflightError("دفتر مالکیت نمی‌تواند بدون دلایل مسدودسازی معتبر باشد")
    return {"schema":"structural_four_package_preflight_v1",
            "status":"BLOCKED_FOR_COMMIT","commit_allowed":False,
            "project_id":project["id"],"candidate_count":len(rows),
            "candidate_count_by_engine":{k:len(previews[k]["takeoff_candidates"]) for k in EXPECTED},
            "dry_run_boq_count":len(boq),"preview_totals_by_unit":totals,
            "kg_rows":len(unlinked),"unlinked_rebar_candidate_source_ids":missing_bar_link,
            "ownership_preview_physical_bars":len(paid),
            "ownership_blockers":deepcopy(owner_blockers),
            "blockers":blockers,"new_files_only":True,
            "limitations":"No snapshot commit, database write, pricebook entry, Windows test or signed engineering approval"}
