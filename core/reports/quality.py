"""Commercial report quality layer: stable columns, totals and RTL metadata."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

FA_COLUMNS=("ردیف","منبع","کد فهرست‌بها","شرح","مقدار","واحد","بهای واحد","مبلغ")
EN_COLUMNS=("No.","Source","Price code","Description","Quantity","Unit","Unit price","Amount")

def prepare_rows(rows: Iterable[dict], language="fa") -> list[dict]:
    out=[]
    for i,r in enumerate(rows,1):
        q=Decimal(str(r.get("quantity",0) or 0)); p=r.get("unit_price")
        amount="" if p in (None,"") else (q*Decimal(str(p))).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        if language=="fa":
            out.append({"ردیف":i,"منبع":r.get("source",""),"کد فهرست‌بها":r.get("price_code",""),
                        "شرح":r.get("description",""),"مقدار":float(q),"واحد":r.get("unit",""),
                        "بهای واحد":"" if p in (None,"") else float(p),"مبلغ":"" if amount=="" else float(amount)})
        else:
            out.append({"No.":i,"Source":r.get("source",""),"Price code":r.get("price_code",""),
                        "Description":r.get("description",""),"Quantity":float(q),"Unit":r.get("unit",""),
                        "Unit price":"" if p in (None,"") else float(p),"Amount":"" if amount=="" else float(amount)})
    return out

def summary(rows: Iterable[dict]) -> dict:
    rows=list(rows); amounts=[Decimal(str(r.get("مبلغ",r.get("Amount",0)) or 0)) for r in rows]
    return {"line_count":len(rows),"grand_total":float(sum(amounts,Decimal("0"))),"rtl":True}
