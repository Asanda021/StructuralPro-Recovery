"""Deterministic offline QA used by Local AI before optional local LLM analysis."""
from __future__ import annotations
from typing import Any
class ProjectQA:
    def run(self, project:dict[str,Any]) -> list[dict[str,Any]]:
        issues=[]
        if not project.get("name"): issues.append({"severity":"error","code":"missing_project_name","message":"نام پروژه وارد نشده است."})
        for i,r in enumerate(project.get("takeoffs",[]) or [],1):
            nested=(r.get("quantities") or [{}])[0] if isinstance(r.get("quantities"),list) else {}
            q=r.get("quantity", nested.get("amount")); unit=str(r.get("unit", nested.get("unit",""))).strip()
            if q is None: issues.append({"severity":"error","row":i,"code":"missing_quantity"})
            else:
                try:
                    if float(q)<0: issues.append({"severity":"error","row":i,"code":"negative_quantity"})
                except (TypeError,ValueError): issues.append({"severity":"error","row":i,"code":"invalid_quantity"})
            if not unit: issues.append({"severity":"warning","row":i,"code":"missing_unit"})
            if not r.get("price_code", nested.get("price_code")): issues.append({"severity":"warning","row":i,"code":"missing_price_code"})
        return issues
