"""Validation and reproducibility helpers for annual price-list datasets."""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Iterable
from core.pricing.catalog import PriceItem

class PriceDataset:
    def validate(self, items: Iterable[PriceItem]) -> list[str]:
        rows=list(items); errors=[]; seen=set()
        for i,x in enumerate(rows,1):
            key=(int(x.year),str(x.code).strip())
            if key in seen: errors.append(f"ردیف {i}: کد تکراری {x.code} در سال {x.year}")
            seen.add(key)
            if int(x.year)<1300: errors.append(f"ردیف {i}: سال نامعتبر")
            if not str(x.group).strip() or not str(x.chapter).strip(): errors.append(f"ردیف {i}: گروه/فصل ناقص")
            if not str(x.code).strip(): errors.append(f"ردیف {i}: کد خالی")
            if not str(x.description).strip(): errors.append(f"ردیف {i}: شرح خالی")
            if not str(x.unit).strip(): errors.append(f"ردیف {i}: واحد خالی")
            if float(x.unit_price)<0: errors.append(f"ردیف {i}: قیمت منفی")
        return errors

    def manifest(self, items: Iterable[PriceItem], source="local") -> dict:
        rows=[asdict(x) for x in items]
        payload=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        years=sorted({x["year"] for x in rows},reverse=True)
        return {"source":source,"count":len(rows),"years":years,
                "sha256":sha256(payload).hexdigest(),"valid":not self.validate([PriceItem(**x) for x in rows])}
