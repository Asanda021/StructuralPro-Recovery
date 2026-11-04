"""Explicit contract pricing mode at the start of a payment statement.

The ordinary pricebook option retains existing approved-source gates.
The private-contract option uses independently reviewed contractual BOQ
unit rates with a content-hashed agreement. Never infer missing prices,
approve an unreviewed estimate, or change mode after existing periods.
"""
from __future__ import annotations
from hashlib import file_digest
from pathlib import Path
from core.commercial.exact_values import number

MODES={"pricebook":"فهرست‌بهایی","contract_rates":"بدون فهرست‌بها؛ نرخ قراردادی"}
def _hash(path):
    p=Path(path).resolve(strict=True)
    if not p.is_file():raise ValueError("مدرک قرارداد باید فایل موجود باشد")
    if p.stat().st_size>100*1024*1024:raise ValueError("مدرک قرارداد از حد امن بزرگ‌تر است")
    with p.open("rb") as fd: return str(p),file_digest(fd,"sha256").hexdigest()

def statement_mode(project):
    raw=project.get("statement_pricing_mode")
    if raw is None:
        # Compatibility for preexisting projects/periods which always required
        # the pricebook path. New UI still explicitly prompts before entry.
        return "pricebook"
    if raw not in MODES:raise ValueError("مبنای صورت‌وضعیت پروژه معتبر نیست")
    return raw

ENTRY_STYLES={
    "prefilled":"مبلغ قرارداد از ابتدا نمایش داده شود",
    "operator_blank":"خانه مبلغ تا زمان ورود اپراتور خالی باشد",
}


def choose_statement_mode(project,mode,contract_price_entry="prefilled"):
    if mode not in MODES:raise ValueError("نوع صورت‌وضعیت معتبر نیست")
    if contract_price_entry not in ENTRY_STYLES:
        raise ValueError("نحوه ورود مبلغ قرارداد نامعتبر است")
    previous=project.get("statement_pricing_mode")
    original_mode=previous if previous is not None else "pricebook"
    periods=project.get("statement_periods") or project.get("statement_amendments")
    if periods and (original_mode!=mode or (
        mode=="contract_rates" and
        project.get("statement_contract_price_entry","prefilled")!=contract_price_entry
    )):
        raise ValueError("پس از ثبت دوره یا اصلاحیه، مبنای قیمت و نحوه ورود مبلغ قابل تغییر نیست")
    old_style=project.get("statement_contract_price_entry","prefilled")
    if mode=="contract_rates" and contract_price_entry=="operator_blank" and (
        original_mode!="contract_rates" or old_style!="operator_blank"
    ):
        for row in project.get("boq",[]):
            # Preserve original source price for evidence but NEVER treat it
            # as the operator's reviewed contract rate.
            if "pre_operator_unit_price" not in row:
                row["pre_operator_unit_price"]=row.get("unit_price")
            row["unit_price"]=None
            row["operator_price_review_status"]="AWAITING_OPERATOR"
    if previous!=mode or (mode=="contract_rates" and old_style!=contract_price_entry):
        project.pop("statement_contract_rate_review",None)
    project["statement_pricing_mode"]=mode
    project["statement_contract_price_entry"]=contract_price_entry if mode=="contract_rates" else None
    return project


def set_operator_contract_price(project,price_code,unit_price,operator):
    """Fill an intentionally blank rate, audit the operator and invalidate approval."""
    if statement_mode(project)!="contract_rates":
        raise ValueError("این پروژه در حالت بدون فهرست‌بها نیست")
    if project.get("statement_periods") or project.get("statement_amendments"):
        raise ValueError("نرخ قراردادی پس از ثبت دوره باید از مسیر اصلاحیه بازبینی شود")
    name=str(operator or "").strip()
    if not name or len(name)>128:
        raise ValueError("نام اپراتور واردکننده نرخ لازم است")
    code=str(price_code or "").strip()
    if not code:raise ValueError("کد ردیف قراردادی لازم است")
    from decimal import Decimal,InvalidOperation
    try: amount=Decimal(str(unit_price))
    except (InvalidOperation,TypeError,ValueError) as exc:
        raise ValueError("مبلغ قرارداد عدد معتبر نیست") from exc
    if not amount.is_finite() or amount<=0:
        raise ValueError("مبلغ قرارداد باید مثبت و صریح باشد؛ خانه خالی صفر نیست")
    matches=[x for x in project.get("boq",[]) if str(x.get("price_code","")).strip()==code]
    if len(matches)!=1:raise ValueError("کد ردیف BOQ یافت نشد یا تکراری است")
    row=matches[0]
    before=row.get("unit_price")
    row["unit_price"]=str(amount)
    row["operator_price_review_status"]="ENTERED_AWAITING_CONTRACT_REVIEW"
    project.setdefault("statement_contract_rate_edits",[]).append({
        "code":code,"old_rate":before,"new_rate":str(amount),
        "operator":name,"state":"RECORDED_UNAPPROVED",
    })
    project.pop("statement_contract_rate_review",None)
    return {"code":code,"rate":str(amount),"operator":name,
            "ready_for_payment":False}


def operator_price_status(project):
    if statement_mode(project)!="contract_rates":
        raise ValueError("وضعیت مبلغ اپراتور فقط برای بدون فهرست‌بها است")
    rows=project.get("boq") or []
    missing=[str(x.get("price_code") or x.get("item_code") or "") for x in rows
             if x.get("unit_price") is None or str(x.get("unit_price")).strip()==""]
    return {"style":project.get("statement_contract_price_entry") or "prefilled",
            "total_rows":len(rows),"missing_codes":missing,
            "ready_for_review":bool(rows) and not missing}


def review_contract_rates(project,agreement_path,reviewer):
    if statement_mode(project)!="contract_rates":
        raise ValueError("این پروژه فهرست‌بهایی است")
    if not str(reviewer).strip():raise ValueError("نام بازبین نرخ‌های قرارداد الزامی است")
    from core.reports.aec_office_package import audit_boq
    audit=audit_boq(project,require_pricebook=False)
    status=operator_price_status(project)
    if status["missing_codes"]:
        raise ValueError("مبلغ ردیف‌های قراردادی وارد نشده: "+", ".join(status["missing_codes"][:10]))
    if not audit.get("pricing_complete"):raise ValueError("همه ردیف‌های BOQ باید نرخ قرارداد صریح داشته باشند")
    boq=project.get("boq") or []
    if not boq:raise ValueError("BOQ پروژه برای ثبت نرخ قرارداد خالی است")
    rates={}
    for row in boq:
        code=str(row.get("price_code") or "").strip()
        if not code or code in rates:raise ValueError("کد نرخ قرارداد خالی یا تکراری است")
        amount=number(row.get("unit_price"),"نرخ قراردادی")
        if amount<0:raise ValueError("نرخ قراردادی منفی مجاز نیست")
        rates[code]={"unit":str(row.get("unit")),"rate":str(amount),
                     "item_code":str(row.get("item_code"))}
    path,digest=_hash(agreement_path)
    project["statement_contract_rate_review"]={
        "status":"reviewed_draft","path":path,"sha256":digest,
        "reviewed_by":str(reviewer).strip(),"rates":rates,
    }
    return project["statement_contract_rate_review"]

def validate_statement_pricing(project):
    mode=statement_mode(project)
    from core.reports.aec_office_package import audit_boq
    if mode=="pricebook":
        audit_boq(project,require_pricebook=True)
        return {"mode":mode,"source":"APPROVED_PRICEBOOK"}
    audit=audit_boq(project,require_pricebook=False)
    proof=project.get("statement_contract_rate_review")
    if not isinstance(proof,dict) or proof.get("status")!="reviewed_draft":
        raise ValueError("در حالت بدون فهرست‌بها، نرخ‌های قرارداد و مدرک آنها باید بازبینی شوند")
    if not audit.get("pricing_complete"):
        raise ValueError("همه ردیف‌های صورت‌وضعیت باید قیمت واحد قرارداد داشته باشند")
    _,digest=_hash(proof.get("path",""))
    if digest!=proof.get("sha256"):
        raise ValueError("محتوای قرارداد نرخ‌ها تغییر کرده است؛ بازبینی مجدد الزامی است")
    if not str(proof.get("reviewed_by","")).strip():
        raise ValueError("بازبین نرخ‌ها ثبت نشده است")
    rows=project.get("boq") or []
    rates=proof.get("rates")
    if not isinstance(rates,dict) or len(rates)!=len(rows):
        raise ValueError("بانک نرخ‌های قرارداد با BOQ تطبیق ندارد")
    for row in rows:
        code=str(row.get("price_code") or "")
        origin=rates.get(code)
        if not isinstance(origin,dict):
            raise ValueError("کد نرخ قراردادی فاقد مرجع است")
        if (origin["unit"]!=str(row.get("unit")) or
            origin["item_code"]!=str(row.get("item_code")) or
            number(origin["rate"],"نرخ ثبت‌شده")!=number(row.get("unit_price"),"نرخ BOQ")):
            raise ValueError("نرخ یا واحد BOQ با نسخه بازبینی‌شده قرارداد مغایر است")
    return {"mode":mode,"source":"REVIEWED_CONTRACT_RATE_DRAFT",
            "agreement_sha256":digest,"reviewed_by":proof["reviewed_by"]}
