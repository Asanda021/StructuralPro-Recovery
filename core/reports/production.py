"""Production-grade report preparation with stable Persian/English columns."""
from __future__ import annotations
from typing import Iterable
from core.reports.quality import prepare_rows

PERSIAN_COLUMNS={"item_no":"ردیف","price_code":"کد","description":"شرح","quantity":"مقدار","unit":"واحد","unit_price":"بهای واحد","total":"مبلغ","source":"منبع"}

def prepare_report(rows:Iterable[dict], language="fa"):
    normalized=prepare_rows(list(rows),language)
    if language=="fa":
        return [{PERSIAN_COLUMNS.get(k,k):v for k,v in r.items()} for r in normalized]
    return normalized

def totals(rows):
    rows=list(rows); return {"count":len(rows),"quantity":sum(float(r.get("مقدار",r.get("quantity",0)) or 0) for r in rows),
                             "amount":sum(float(r.get("مبلغ",r.get("total",0)) or 0) for r in rows)}
