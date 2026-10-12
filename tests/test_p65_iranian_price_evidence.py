from core.estimate.iran_price_evidence_v1 import IranPriceEvidence,validate,fingerprint
def e(code="1001"): return IranPriceEvidence(code,"concrete","m3",1000000,"IRR","official-source","price-list","1405","2026-03-20","2026-10-04")
def test_valid(): assert len(fingerprint((e(),)))==64
def test_empty():
    try: validate(())
    except ValueError: return
    assert False
def test_negative():
    x=e(); x=IranPriceEvidence(x.item_code,x.description,x.unit,-1,x.currency,x.source,x.list_name,x.version,x.effective_date,x.observed_at)
    try: validate((x,))
    except ValueError: return
    assert False
def test_duplicate():
    try: validate((e(),e()))
    except ValueError: return
    assert False
