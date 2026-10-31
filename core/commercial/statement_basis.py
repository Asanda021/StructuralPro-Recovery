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

def choose_statement_mode(project,mode):
    if mode not in MODES:raise ValueError("نوع صورت‌وضعیت معتبر نیست")
    previous=project.get("statement_pricing_mode")
    effective_previous = previous if previous is not None else "pricebook"
    if effective_previous!=mode and (
        project.get("statement_periods") or project.get("statement_amendments")
    ):
        raise ValueError("پس از ثبت دوره یا اصلاحیه، مبنای صورت‌وضعیت قابل تغییر نیست")
    if previous!=mode:
        project.pop("statement_contract_rate_review",None)
    project["statement_pricing_mode"]=mode
    return project

def review_contract_rates(project,agreement_path,reviewer):
    if statement_mode(project)!="contract_rates":
        raise ValueError("این پروژه فهرست‌بهایی است")
    if not str(reviewer).strip():raise ValueError("نام بازبین نرخ‌های قرارداد الزامی است")
    from core.reports.aec_office_package import audit_boq
    audit=audit_boq(project,require_pricebook=False)
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
