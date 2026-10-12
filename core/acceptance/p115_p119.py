"""Production acceptance for P115-P119.
P115 estimate finalization hardening; P116 scenario/BOQ completeness;
P117 validated import; P118 professional report schema; P119 audit/provenance.
"""
from __future__ import annotations
from decimal import Decimal
from core.takeoff.estimating import build_professional_estimate
from core.takeoff.estimate import build_estimate
from core.engineering.production_quantity_scenarios_v1 import production_scenarios
from core.integrations.interchange_v2 import validate_import_rows, import_summary
from core.report.professional_reports_v2 import ReportRow, build_report, export_schema
from core.audit.traceability import TraceNode, AuditEvent, AuditTrail, TraceGraph

def run_p115():
    rows=[{"source":"takeoff:A1","source_type":"drawing","price_code":"C-001",
           "description":"Concrete","quantity":10,"unit":"m3","unit_price":100}]
    result=build_professional_estimate(rows,factors={"overhead":.1},strict_prices=True)
    return {"verified":result["finalizable"],"grand_total":result["cost"]["grand_total"],
            "unresolved":result["price_mapping"]["unresolved"]}

def run_p116():
    scenarios=production_scenarios()
    estimate=build_estimate(
        [{"price_code":"C-001","description":"Concrete","quantity":10,"unit":"m3","unit_price":100}],
        factors={"overhead":.1})
    valid=(len(scenarios)>=6 and estimate["finalizable"] and
           all(x["stock_bar_count"]>=0 and x["waste_length_m"]>=0 for x in scenarios))
    return {"verified":valid,"scenario_count":len(scenarios),
            "concrete_m3":sum(x["concrete_m3"] for x in scenarios),
            "rebar_kg":sum(x["rebar_kg"] for x in scenarios)}

def run_p117():
    imported=validate_import_rows([
        {"price_code":"C-001","description":"Concrete","quantity":"10","unit":"m3","unit_price":"100"},
        {"price_code":"R-001","description":"Rebar","quantity":250,"unit":"kg","unit_price":50000},
    ])
    summary=import_summary(imported)
    return {"verified":summary["row_count"]==2 and summary["quantity_total"]==260,
            "row_count":summary["row_count"],"quantity_total":summary["quantity_total"]}

def run_p118():
    report=build_report([
        ReportRow("C-001","Concrete","m3",Decimal("10"),"takeoff:A1",Decimal("1000"),"IRR"),
        ReportRow("R-001","Rebar","kg",Decimal("250"),"takeoff:A2",Decimal("12500000"),"IRR"),
    ],report_type="estimate",title="Production Estimate",project_id="P118",
       branding={"company":"StructuralPro"})
    schema=export_schema(report,format="xlsx")
    return {"verified":len(schema["rows"])==2 and bool(schema["fingerprint"]),
            "fingerprint":schema["fingerprint"],"formats":["xlsx","pdf","json"]}

def run_p119():
    g=TraceGraph()
    nodes=[
        TraceNode("d1","drawing",source="plan.pdf",external_id="S1",revision="R1"),
        TraceNode("t1","takeoff",source="takeoff:S1",external_id="S1",revision="R1",quantity=10,unit="m3",item_code="C-001"),
        TraceNode("b1","boq",source="boq",external_id="C-001",quantity=10,unit="m3",item_code="C-001"),
        TraceNode("e1","estimate",source="estimate",external_id="E1",quantity=1000,unit="IRR"),
    ]
    for n in nodes:g.add_node(n)
    g.link("d1","t1"); g.link("t1","b1"); g.link("b1","e1")
    trail=AuditTrail([AuditEvent("evt1","created","d1",user="system",revision="R1",
                                  after={"source":"plan.pdf"})])
    validation=g.validate()
    return {"verified":validation["valid"] and len(g.lineage("e1"))==3 and len(trail.events())==1,
            "nodes":validation["node_count"],"edges":validation["edge_count"],
            "lineage":g.lineage("e1")}

def run_all():
    return {f"P{i}":fn() for i,fn in [(115,run_p115),(116,run_p116),(117,run_p117),(118,run_p118),(119,run_p119)]}
