"""P81 — deterministic manifest for extracted pricebook sources."""
from dataclasses import asdict
from hashlib import sha256
import json

def source_manifest(rows):
    if not rows: raise ValueError("no rows")
    groups={}
    for r in rows:
        key=(r.year,r.discipline,r.source_file,r.source_sha256)
        g=groups.setdefault(key,{"rows":0,"priced_rows":0,"chapters":set(),"item_codes":set()})
        g["rows"]+=1
        g["priced_rows"]+=r.unit_price is not None
        g["item_codes"].add(r.item_code)
    out=[]
    for (year,discipline,file,digest),g in sorted(groups.items()):
        out.append({"year":year,"discipline":discipline,"source_file":file,
                    "source_sha256":digest,"rows":g["rows"],
                    "priced_rows":g["priced_rows"],
                    "unpriced_rows":g["rows"]-g["priced_rows"],
                    "item_code_count":len(g["item_codes"])})
    canonical=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return {"sources":out,"fingerprint":sha256(canonical.encode()).hexdigest()}

def coverage_gate(manifest, expected_disciplines):
    found={x["discipline"] for x in manifest["sources"]}
    missing=sorted(set(expected_disciplines)-found)
    return {"expected":sorted(expected_disciplines),"found":sorted(found),
            "missing":missing,"green":not missing and all(x["rows"]>0 for x in manifest["sources"])}
