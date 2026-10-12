"""Revision impact propagation from source changes to quantities, BOQ and cost."""
from __future__ import annotations
from core.revisions.intelligence import compare_project_revisions, summarize_impact

def build_impact_report(before,after,before_boq=(),after_boq=(),before_estimate=None,after_estimate=None):
    changes=compare_project_revisions(before,after)
    boq_changes=compare_project_revisions(before_boq,after_boq)
    cost_before=float((before_estimate or {}).get("total",0) or 0)
    cost_after=float((after_estimate or {}).get("total",0) or 0)
    return {"changes":changes,"summary":summarize_impact(changes),"boq_changes":boq_changes,
            "cost_delta":cost_after-cost_before,
            "finalizable":not any(x.get("review_required") and x.get("review_status")!="approved" for x in changes)}
