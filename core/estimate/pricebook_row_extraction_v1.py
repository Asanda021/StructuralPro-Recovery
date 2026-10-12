"""P77 — evidence-first pricebook row extraction."""
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
import csv, json

@dataclass(frozen=True)
class NormalizedPriceRow:
    year:int
    discipline:str
    item_code:str
    description:str
    unit:str
    unit_price:float|None
    source_sha256:str
    source_file:str

def _text(v): return "" if v is None else str(v).strip()

def _price(v):
    s=_text(v).replace(",","").replace("٬","")
    if not s: return None
    try: return float(s)
    except ValueError: return None

def _row(r,year,discipline,digest,name):
    code=_text(r.get("item_code") or r.get("code") or r.get("ردیف"))
    desc=_text(r.get("description") or r.get("شرح"))
    unit=_text(r.get("unit") or r.get("واحد"))
    raw_price=next((r[key] for key in ("unit_price", "price", "بهای واحد")
                    if key in r and r[key] is not None and r[key] != ""), None)
    price=_price(raw_price)
    return NormalizedPriceRow(year,discipline,code,desc,unit,price,digest,name)

def extract_csv(path,year,discipline):
    p=Path(path); digest=sha256(p.read_bytes()).hexdigest(); rows=[]
    with p.open("r",encoding="utf-8-sig",newline="") as fh:
        for r in csv.DictReader(fh):
            x=_row(r,year,discipline,digest,p.name)
            if x.item_code or x.description: rows.append(x)
    return rows

def extract_json(path,year,discipline):
    p=Path(path); digest=sha256(p.read_bytes()).hexdigest()
    data=json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data,dict): data=data.get("rows",[])
    return [x for r in data for x in [_row(r,year,discipline,digest,p.name)] if x.item_code or x.description]

def extract_xlsx(path,year,discipline):
    from openpyxl import load_workbook
    p=Path(path); digest=sha256(p.read_bytes()).hexdigest(); out=[]
    wb=load_workbook(p,data_only=True,read_only=True)
    for ws in wb.worksheets:
        values=list(ws.values)
        if not values: continue
        headers=[_text(v) for v in values[0]]
        for vals in values[1:]:
            r=dict(zip(headers,vals))
            x=_row(r,year,discipline,digest,p.name)
            if x.item_code or x.description: out.append(x)
    return out

def validate_rows(rows):
    if not rows: raise ValueError("no pricebook rows extracted")
    if any(not r.item_code and not r.description for r in rows): raise ValueError("row without code and description")
    return {"rows":len(rows),"priced_rows":sum(r.unit_price is not None for r in rows),
            "unpriced_rows":sum(r.unit_price is None for r in rows),
            "source_hashes":sorted({r.source_sha256 for r in rows})}
