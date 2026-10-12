from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class PriceRow:
    year:int; group:str; chapter:str; code:str; description:str; unit:str; unit_price:float

REQUIRED={"year","group","chapter","code","description","unit","unit_price"}
class AnnualPriceImporter:
    def validate(self, rows: Iterable[dict]) -> list[str]:
        errors=[]
        for n,row in enumerate(rows,1):
            missing=REQUIRED-set(row)
            if missing: errors.append(f"row {n}: missing {', '.join(sorted(missing))}"); continue
            try:
                year=int(row["year"]); price=float(row["unit_price"])
                if year<1300: raise ValueError("invalid year")
                if price<0: raise ValueError("negative price")
            except (TypeError,ValueError) as exc: errors.append(f"row {n}: {exc}")
            if not str(row["code"]).strip(): errors.append(f"row {n}: empty code")
        return errors
    def read_csv(self,path:str|Path)->list[dict]:
        with Path(path).open("r",encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))
    def convert(self,rows:Iterable[dict])->list[PriceRow]:
        rows=list(rows); errors=self.validate(rows)
        if errors: raise ValueError("; ".join(errors))
        return [PriceRow(int(r["year"]),str(r["group"]),str(r["chapter"]),str(r["code"]),str(r["description"]),str(r["unit"]),float(r["unit_price"])) for r in rows]
