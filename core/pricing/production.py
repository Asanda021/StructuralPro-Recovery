"""Validated price-dataset and analysis helpers; no official data is fabricated."""
from __future__ import annotations
from typing import Any

REQUIRED={"year","group","chapter","code","description","unit","unit_price"}

def validate_dataset_rows(rows, expected_year=None) -> dict[str,Any]:
    rows=list(rows); errors=[]; codes=set()
    for i,row in enumerate(rows,1):
        missing=sorted(REQUIRED-set(row))
        if missing: errors.append({"row":i,"code":"missing_fields","fields":missing}); continue
        try: year=int(row["year"]); price=float(row["unit_price"])
        except (TypeError,ValueError): errors.append({"row":i,"code":"invalid_numeric"}); continue
        if expected_year is not None and year != int(expected_year): errors.append({"row":i,"code":"wrong_year"})
        if not str(row["code"]).strip(): errors.append({"row":i,"code":"empty_code"})
        if price < 0: errors.append({"row":i,"code":"negative_price"})
        if row["code"] in codes: errors.append({"row":i,"code":"duplicate_code"})
        codes.add(row["code"])
    return {"valid":not errors,"rows":len(rows),"errors":errors}

def price_analysis(quantity: float, unit_price: float, factors=None) -> dict[str,float]:
    q=float(quantity); base=q*float(unit_price)
    factor_total=1.0
    for f in factors or (): factor_total*=float(f)
    return {"quantity":q,"unit_price":float(unit_price),"factor":factor_total,"amount":round(base*factor_total, 10)}
