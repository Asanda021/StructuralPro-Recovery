"""End-to-end drawing -> takeoff -> mapping -> assembly -> estimate workflow."""
from __future__ import annotations
from typing import Any
import math
from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
from core.ai.takeoff_assistant import LocalTakeoffAssistant
from core.takeoff.assemblies import AssemblyLibrary

class TakeoffWorkflow:
    def __init__(self,price_catalog=None):
        self.drawing=UnifiedDrawingTakeoff(price_resolver=price_catalog)
        self.ai=LocalTakeoffAssistant()
        self.assemblies=AssemblyLibrary()
        self.catalog=price_catalog

    def inspect(self,path):
        return self.drawing.inspect(path)

    def confirm(self,inspection,selected=None):
        rows=inspection.get("candidates",[]) or []
        if selected is None:
            raise ValueError("برای تأیید متره، ردیف‌ها باید صریحاً انتخاب شوند")
        selected=set(selected)
        if any(isinstance(i, bool) or not isinstance(i, int) or i < 1 or i > len(rows) for i in selected):
            raise ValueError("شناسه ردیف انتخاب‌شده معتبر نیست")
        return [dict(r,confirmed=True) for i,r in enumerate(rows,1) if i in selected]

    def map_price_codes(self,rows,catalog_rows):
        mapped=self.ai.suggest_mapping(rows,catalog_rows)
        out=[]
        for row,suggestion in zip(rows,mapped):
            x=dict(row); x["price_suggestions"]=suggestion["suggestions"]
            if suggestion["suggestions"] and not x.get("price_code"):
                x["needs_price_confirmation"]=True
            out.append(x)
        return out

    def apply_assembly(self,row,assembly_code):
        x=dict(row); x["assembly_code"]=assembly_code
        x["assembly"]=self.assemblies.expand(assembly_code,float(x.get("quantity",0)))
        x["assembly_total"]=sum(float(c["cost"]) for c in x["assembly"])
        return x

    def graphical_rows(self, session, selected_ids=None):
        """Convert a DrawingTakeoffSession into validated BOQ-ready rows."""
        if not hasattr(session, "boq_rows") or not hasattr(session, "validate"):
            raise TypeError("session must be a DrawingTakeoffSession")
        validation = session.validate()
        if not validation["valid"]:
            raise ValueError("؛ ".join(validation["issues"]))
        return session.boq_rows(selected_ids)

    def build_estimate(self,rows,price_lookup=None):
        result=[]
        for row in rows:
            x=dict(row)
            if x.get("needs_price_confirmation"):
                raise ValueError("کد قیمت پیشنهادی باید ابتدا توسط کاربر تأیید شود")
            raw_quantity=x.get("quantity")
            if isinstance(raw_quantity, bool): raise ValueError("مقدار متره باید عددی باشد")
            q=float(raw_quantity)
            if not math.isfinite(q) or q<0: raise ValueError("مقدار متره باید متناهی و نامنفی باشد")
            price=x.get("unit_price")
            if price_lookup is not None and x.get("price_code") in price_lookup:
                price=price_lookup[x["price_code"]]
            if price is None or isinstance(price, bool):
                raise ValueError("بهای واحد معتبر وارد نشده است")
            price=float(price)
            if not math.isfinite(price) or price<0: raise ValueError("بهای واحد باید متناهی و نامنفی باشد")
            x["unit_price"]=price
            x["total"]=q*price
            if not math.isfinite(x["total"]): raise ValueError("مبلغ برآورد باید متناهی باشد")
            result.append(x)
        return result

    def run(self,path,catalog_rows=None,selected=None,price_lookup=None):
        inspection=self.inspect(path)
        confirmed=self.confirm(inspection,selected)
        mapped=self.map_price_codes(confirmed,catalog_rows or [])
        estimated=self.build_estimate(mapped,price_lookup)
        return {"inspection":inspection,"rows":estimated,
                "summary":{"items":len(estimated),"total":sum(x["total"] for x in estimated)}}

