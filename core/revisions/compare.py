"""Revision comparison for takeoff quantities and costs."""
from __future__ import annotations
def _key(r): return str(r.get("price_code") or r.get("code") or r.get("description") or "").strip()
def compare_rows(old_rows,new_rows):
    old={_key(x):x for x in old_rows if _key(x)}; new={_key(x):x for x in new_rows if _key(x)}
    keys=list(dict.fromkeys([*old.keys(),*new.keys()])); out=[]
    for k in keys:
        a,b=old.get(k),new.get(k)
        aq=float((a or {}).get("quantity",0) or 0); bq=float((b or {}).get("quantity",0) or 0)
        ap=float((a or {}).get("total",0) or 0); bp=float((b or {}).get("total",0) or 0)
        status="added" if a is None else ("removed" if b is None else ("changed" if aq!=bq or ap!=bp else "unchanged"))
        out.append({"key":k,"status":status,"old_quantity":aq,"new_quantity":bq,"quantity_delta":bq-aq,
                    "old_total":ap,"new_total":bp,"total_delta":bp-ap})
    return out
def summary(changes):
    return {"added":sum(x["status"]=="added" for x in changes),"removed":sum(x["status"]=="removed" for x in changes),
            "changed":sum(x["status"]=="changed" for x in changes),"unchanged":sum(x["status"]=="unchanged" for x in changes),
            "quantity_delta":sum(x["quantity_delta"] for x in changes),"cost_delta":sum(x["total_delta"] for x in changes)}
