"""Validated period progress, deductions, payments and balances."""
from __future__ import annotations
import math

def build_progress(lines, *, deductions=None, payments=None):
    rows=[]; contract_total=completed_total=current_total=0.0; seen=set()
    deduction_values=[float(x) for x in (deductions or [])]
    payment_values=[float(x) for x in (payments or [])]
    if any(not math.isfinite(x) or x<0 for x in deduction_values+payment_values):
        raise ValueError("deductions/payments must be finite and non-negative")
    for x in lines:
        d=x if isinstance(x,dict) else vars(x)
        code=str(d.get("code") or d.get("price_code") or d.get("source") or "").strip()
        if code and code in seen: raise ValueError(f"duplicate progress line: {code}")
        if code: seen.add(code)
        cq=float(d.get("contract_quantity",0) or 0); prev=float(d.get("previous_quantity",0) or 0)
        cur=float(d.get("current_quantity",0) or 0); price=float(d.get("unit_price",0) or 0)
        vals=(cq,prev,cur,price)
        if any(not math.isfinite(v) or v<0 for v in vals): raise ValueError("quantities and prices must be finite and non-negative")
        if prev>cq or cur>max(cq-prev,0): raise ValueError(f"progress exceeds contract for {code or 'line'}")
        cumulative=prev+cur; contract_amount=cq*price; completed_amount=cumulative*price
        current_amount=cur*price
        rows.append({**d,"cumulative_quantity":cumulative,"remaining_quantity":cq-cumulative,
            "progress_percent":0 if cq==0 else cumulative/cq*100,"contract_amount":contract_amount,
            "current_amount":current_amount,"completed_amount":completed_amount,
            "over_contract_quantity":0.0})
        contract_total+=contract_amount; completed_total+=completed_amount; current_total+=current_amount
    deduction_total=sum(deduction_values); payment_total=sum(payment_values)
    gross=current_total; payable=max(gross-deduction_total,0)
    return {"lines":rows,"contract_total":contract_total,"completed_total":completed_total,
            "current_total":current_total,"gross_current":gross,"deductions":deduction_total,
            "payable_current":payable,"payments":payment_total,"balance_current":payable-payment_total,
            "remaining_contract":max(contract_total-completed_total,0),
            "progress_percent":0 if contract_total==0 else completed_total/contract_total*100}
