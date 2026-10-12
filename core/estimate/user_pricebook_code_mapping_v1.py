"""P84/P87 — deterministic pricebook mapping by normalized item code and unit."""
from dataclasses import dataclass
from core.estimate.pricebook_ingestion_v1 import PriceRow
from core.estimate.item_code_normalization_v1 import code_key

@dataclass(frozen=True)
class CodeUnitMatch:
    takeoff_id:str
    item_code:str
    unit:str
    exact:bool

def index_code_unit(rows, year, discipline):
    selected=[r for r in rows if r.year==year and r.discipline==discipline and r.item_code and r.unit and r.unit_price is not None]
    index={}
    for r in selected:
        key=code_key(r.item_code,r.unit)
        if key in index and index[key].rate != r.unit_price:
            raise ValueError("conflicting rates for normalized item code/unit")
        index[key]=PriceRow(r.year,"",key[0],r.description,r.unit.strip(),r.unit_price,"IRR")
    return index

def map_by_code_unit(takeoff_rows, rows, year, discipline):
    index=index_code_unit(rows,year,discipline)
    matches=[]; unresolved=[]
    for item in takeoff_rows:
        key=code_key(item.get("item_code",""),item.get("unit",""))
        if key in index:
            matches.append(CodeUnitMatch(str(item["takeoff_id"]),key[0],key[1],True))
        else:
            unresolved.append(str(item["takeoff_id"]))
    return {"matches":matches,"unresolved":unresolved,"green":not unresolved,"count":len(matches)}
