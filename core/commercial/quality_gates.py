"""Cross-cutting quality gates for commercial data."""
import math

def validate_money(value):
    v=float(value)
    if not math.isfinite(v) or v<0: raise ValueError("invalid monetary value")
    return v

def validate_quantity(value):
    v=float(value)
    if not math.isfinite(v) or v<0: raise ValueError("invalid quantity")
    return v

def quality_gate(records):
    checked=0
    for r in records:
        if "amount" in r: validate_money(r["amount"])
        if "quantity" in r: validate_quantity(r["quantity"])
        checked+=1
    return {"passed":True,"checked":checked}
