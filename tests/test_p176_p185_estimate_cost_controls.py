from core.drawing.cost_estimate_traceability_v1 import EstimateLineage
from core.drawing.estimate_cost_controls_v1 import EstimateCostControls

def e(i="e1",b="b1",amount=100,c="IRR",status="accepted",src=("s1",)):
    return EstimateLineage(i,b,"E1",2,"m",50,c,amount,src,status)

def test_p176_source_control(): assert EstimateCostControls().controls([e()])[0].status=="accepted"
def test_p177_missing_source_rejects(): assert EstimateCostControls().controls([e(src=())])[0].status=="rejected"
def test_p178_upstream_review_propagates(): assert EstimateCostControls().controls([e(status="review")])[0].status=="review"
def test_p179_currency_gate(): assert EstimateCostControls().controls([e()],required_currency="USD")[0].status=="review"
def test_p180_threshold_gate(): assert EstimateCostControls().controls([e(amount=101)],max_amount=100)[0].status=="review"
def test_p181_totals_by_currency(): assert EstimateCostControls.totals([e(),e("e2","b2",50)])=={"IRR":150.0}
def test_p182_unresolved_is_explicit(): assert len(EstimateCostControls.unresolved(EstimateCostControls().controls([e(status="review")])))==1
def test_p183_fingerprints_stable(): 
    c=EstimateCostControls().controls([e()]); assert EstimateCostControls.fingerprints(c)==EstimateCostControls.fingerprints(c)
def test_p184_duplicate_boq_detection(): assert EstimateCostControls.duplicate_boqs([e(),e("e2","b1")])==("b1",)
def test_p185_deterministic_order():
    c=EstimateCostControls().controls([e("e2","b2"),e("e1","b1")]); assert [x.estimate_id for x in c]==["e1","e2"]
