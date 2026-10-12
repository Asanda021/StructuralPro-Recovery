from __future__ import annotations
from decimal import Decimal
from core.estimate.pricebook_full_building_pricing_v2 import price_full_building_project
from core.estimate.boq_estimate_cost_control_v1 import BOQLine,RateLine,build_estimate,total_estimate
from core.reports.production_acceptance_bundle_v1 import build_acceptance_bundle,validate_acceptance_bundle
from core.reports.production_report_package_v1 import build_report_package,validate_report_package

def _serial_line(x):
    return {k:(str(v) if isinstance(v,Decimal) else v) for k,v in x.__dict__.items()}

def run(takeoff_rows,pricebook_rows,year,project_id,revision,currency="IRR")->dict:
    priced=price_full_building_project(takeoff_rows,pricebook_rows,year)
    boq=tuple(BOQLine(str(x["takeoff_id"]),str(x["item_code"]),str(x.get("description",x["item_code"])),str(x["unit"]),Decimal(str(x["quantity"])),str(x["source_file"]),str(revision)) for x in priced)
    rates=tuple(RateLine(str(x["item_code"]),str(x["unit"]),Decimal(str(x["unit_price"])),currency,str(x["source_file"]),str(year),str(x["source_sha256"])) for x in priced)
    estimate=build_estimate(boq,rates); total=total_estimate(estimate,currency)
    acceptance=build_acceptance_bundle(project_id=project_id,revision=revision,takeoff=takeoff_rows,boq=[_serial_line(x) for x in boq],estimate=[_serial_line(x) for x in estimate],provenance=[x["source_sha256"] for x in priced])
    validate_acceptance_bundle(acceptance)
    report=build_report_package(project_id=project_id,revision=revision,report_data={"total":str(total),"currency":currency,"lines":len(estimate)},export_files=("report.pdf","report.xlsx","report.json"),rtl=True)
    validate_report_package(report)
    return {"takeoff":tuple(priced),"boq":boq,"estimate":estimate,"total":total,"acceptance":acceptance,"report":report}
