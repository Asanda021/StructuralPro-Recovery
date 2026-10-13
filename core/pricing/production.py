"""Validated price-dataset and analysis helpers; no official data is fabricated."""
from __future__ import annotations
import math
from typing import Any

REQUIRED={"year","group","chapter","code","description","unit","unit_price"}

def _finite_nonnegative(value, title):
    if isinstance(value, bool):
        raise ValueError(f"{title} must be a real number")
    try:
        number=float(value)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError(f"{title} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{title} must be finite and non-negative")
    return number

def validate_dataset_rows(rows, expected_year=None) -> dict[str,Any]:
    rows=list(rows); errors=[]; codes=set()
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict):
            errors.append({"row":i,"code":"invalid_row"})
            continue
        missing=sorted(REQUIRED-set(row))
        if missing:
            errors.append({"row":i,"code":"missing_fields","fields":missing})
            continue
        try:
            if isinstance(row["year"], bool):
                raise ValueError("year must be integer")
            year=int(row["year"])
            if str(row["year"]).strip() != str(year):
                raise ValueError("year must be integer")
            price=_finite_nonnegative(row["unit_price"],"unit_price")
        except (TypeError,ValueError,OverflowError):
            errors.append({"row":i,"code":"invalid_numeric"})
            continue
        if expected_year is not None and year != int(expected_year):
            errors.append({"row":i,"code":"wrong_year"})
        for field in ("code","description","unit","group","chapter"):
            if not isinstance(row[field],str) or not row[field].strip():
                errors.append({"row":i,"code":"empty_"+field})
        if row["code"] in codes:
            errors.append({"row":i,"code":"duplicate_code"})
        codes.add(row["code"])
    return {"valid":not errors,"rows":len(rows),"errors":errors}

def price_analysis(quantity: float, unit_price: float, factors=None) -> dict[str,float]:
    q=_finite_nonnegative(quantity,"quantity")
    price=_finite_nonnegative(unit_price,"unit_price")
    factor_total=1.0
    for f in factors or ():
        factor_total*=_finite_nonnegative(f,"factor")
        if not math.isfinite(factor_total):
            raise ValueError("factors overflow")
    amount=q*price*factor_total
    if not math.isfinite(amount):
        raise ValueError("cost overflows")
    return {"quantity":q,"unit_price":price,"factor":factor_total,"amount":round(amount,10)}
