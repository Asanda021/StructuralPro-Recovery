from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow
from core.estimate.pricebook_production_gate_v1 import normalize_rows, coverage_gate
from core.validation.production_e2e_gate_v1 import benchmark_gate

def row(y,d,c,p=100):
    return NormalizedPriceRow(y,d,c,"شرح","m3",p,"a"*64,f"{d}.xlsx")

def test_normalization_and_partial_coverage():
    rows=normalize_rows([row(1404,"ابنیه","۱۲ – ۰۳")])
    assert rows[0].item_code=="12-03"
    report=coverage_gate(rows,years=(1404,),disciplines=("ابنیه",))
    assert report["complete"] and report["rows"]==1

def test_benchmark_gate_green():
    assert benchmark_gate([10,20,30],[10,20,30])["green2"]

def test_benchmark_gate_fail_closed():
    try: benchmark_gate([10,20],[10,25])
    except ValueError: return
    assert False
