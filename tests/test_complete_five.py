from pathlib import Path
from core.drawings.pdf_engine import PDFDrawingEngine, SnapPoint
from core.drawings.ifc_pipeline import normalize_ifc_rows, aggregate_ifc_quantities, map_ifc_to_boq
from core.pricing.factors import FactorRegistry, FactorSet
from core.commercial.progress import build_progress
from core.projects.statement_engine import StatementLine, build_statement

def test_pdf_snap_and_missing_file(tmp_path):
    p=tmp_path/"x.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    e=PDFDrawingEngine(p)
    assert e.path == p
    assert e.snap((10,10),[SnapPoint(12,11)],tolerance=3)==(12,11)

def test_ifc_normalization_levels_duplicates_and_boq_mapping():
    rows=[
      {"global_id":"G1","ifc_type":"IfcWall","name":"Wall","properties":{"Level":"L1"},"quantities":{"Length":5,"Area":12}},
      {"global_id":"G1","ifc_type":"IfcWall","name":"Duplicate","properties":{"Level":"L1"},"quantities":{"Length":7}},
      {"global_id":"G2","ifc_type":"IfcSlab","name":"Slab","properties":{"Storey":"L2"},"quantities":{"Volume":3}},
    ]
    import pytest
    with pytest.raises(ValueError, match="GlobalId تکراری"):
        normalize_ifc_rows(rows)
    rows.pop(1)
    n=normalize_ifc_rows(rows)
    assert len(n)==2 and n[0]["level"]=="L1"
    a=aggregate_ifc_quantities(rows)
    assert a["objects"]==2 and a["by_level"]["L2"]==1 and a["quantity_totals"]["Length"]==5
    mapped=map_ifc_to_boq(rows,{"IfcWall":"W1","IfcSlab":"S1"})
    assert len(mapped["rows"])==3 and mapped["unmapped"]==[]

def test_year_aware_factors():
    r=FactorRegistry([FactorSet(1404,"پایه",{"بالاسری":0.10},source="source-1404"),
                       FactorSet(1405,"پایه",{"بالاسری":0.12},source="source-1405")])
    assert r.years()==[1405,1404]
    assert r.rates(1405,"پایه")["بالاسری"]==0.12
    assert r.describe(1404,"پایه")["source"]=="source-1404"

def test_progress_complete_contract_flow():
    out=build_progress([{"code":"A","contract_quantity":100,"previous_quantity":20,"current_quantity":10,"unit_price":100}],
                        deductions=[50],payments=[100])
    assert (out["cumulative_total"] if "cumulative_total" in out else out["completed_total"]) == 3000
    assert out["remaining_contract"]==7000
    assert out["balance_current"]==850

def test_statement_engine_previous_current_remaining_and_deductions():
    line=StatementLine("A","Concrete","m3",100,200,10,20)
    out=build_statement([line],retention_rate=.1,advance_recovery_rate=.05,other_deduction_rate=.02,advance_paid=1000)
    assert out["gross_current"]==2000
    assert out["gross_cumulative"]==6000
    assert out["retention"]==200
    assert out["advance_recovery"]==100
    assert round(out["payable"],6)==1660

