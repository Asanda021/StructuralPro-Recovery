from core.commercial.estimation import EstimateLine,estimate,progress_claim
from core.commercial.financial_ledger import LedgerEntry,summarize
from core.commercial.sync_contract import make_operation,merge
from core.commercial.ai_review import AISuggestion,gate
from core.commercial.report_contract import build_report
from core.commercial.quality_gates import quality_gate
import pytest

def test_estimate_and_progress():
    a=EstimateLine("A","Concrete",10,100)
    assert estimate([a])["subtotal"]==1000
    assert progress_claim([a],{"A":50})["executed_amount"]==500

def test_ledger():
    x=summarize([LedgerEntry("receivable",100,"R1"),LedgerEntry("commitment",30,"C1")])
    assert x["totals"]["net_position"]==70

def test_sync_conflict_is_not_silently_resolved():
    a=make_operation("project","1",2,{"x":1}); b=make_operation("project","1",2,{"x":2})
    assert merge(a,b)[1]=="conflict"

def test_ai_always_reviewed():
    assert gate([AISuggestion("p1","wall",5,"m",.9)])[0]["needs_confirmation"]

def test_report_is_rtl():
    assert build_report("گزارش","پروژه",{"متره":[]})["meta"]["direction"]=="rtl"

def test_quality_rejects_negative():
    with pytest.raises(ValueError): quality_gate([{"amount":-1}])
