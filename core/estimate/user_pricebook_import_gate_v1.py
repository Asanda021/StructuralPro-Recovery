"""P82 — fail-closed user pricebook import gate.

Accepts normalized rows produced by the existing import/extraction layer and
requires explicit year/discipline plus complete provenance before promotion
to the estimate engine.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import math

def validate_import(rows, year, discipline):
    if not rows:
        return {"green":False,"reason":"no_rows","rows":0,"priced_rows":0,"unpriced_rows":0,"errors":["no rows to import"]}
    errors=[]
    priced=0
    identities=set()
    for i,r in enumerate(rows):
        if r.year != year: errors.append(f"row {i}: year mismatch")
        if r.discipline != discipline: errors.append(f"row {i}: discipline mismatch")
        if not isinstance(r.source_sha256, str) or len(r.source_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in r.source_sha256):
            errors.append(f"row {i}: invalid source hash")
        identity=(r.year, r.discipline, r.item_code or r.description)
        if identity in identities: errors.append(f"row {i}: duplicate identity")
        identities.add(identity)
        if not r.source_file: errors.append(f"row {i}: missing source file")
        if not r.item_code and not r.description: errors.append(f"row {i}: missing identity")
        if r.unit_price is not None:
            try:
                if isinstance(r.unit_price, bool): raise ValueError("boolean price")
                price=float(r.unit_price)
                if not math.isfinite(price) or price < 0: raise ValueError("invalid price")
            except (ValueError, TypeError, OverflowError):
                errors.append(f"row {i}: invalid unit price")
            else: priced += 1
    payload=[asdict(r) for r in rows]
    fp=sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"green":not errors,"year":year,"discipline":discipline,
            "rows":len(rows),"priced_rows":priced,"unpriced_rows":len(rows)-priced,
            "errors":errors,"fingerprint":fp}

def import_gate(rows, year, discipline, require_all_priced=True):
    result=validate_import(rows,year,discipline)
    if require_all_priced and result["unpriced_rows"]:
        result["green"]=False
        result["errors"].append("unpriced rows require review")
    return result
