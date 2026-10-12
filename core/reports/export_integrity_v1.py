"""Report row integrity gate for deterministic multi-format export."""
import hashlib,json,math
REQUIRED=("ردیف","کد","شرح","مقدار","واحد")
def validate_rows(rows):
 errors=[]
 for i,r in enumerate(rows,1):
  for k in REQUIRED:
   if str(r.get(k,"")).strip()=="": errors.append((i,k))
  try:
   q=float(r.get("مقدار",0))
   if not math.isfinite(q) or q<0: errors.append((i,"مقدار"))
  except (TypeError,ValueError): errors.append((i,"مقدار"))
 return errors
def canonical_rows(rows):
 errs=validate_rows(rows)
 if errs: raise ValueError("invalid report rows: "+repr(errs))
 return tuple({k:r.get(k) for k in REQUIRED} for r in rows)
def fingerprint(rows):
 return hashlib.sha256(json.dumps(canonical_rows(rows),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()