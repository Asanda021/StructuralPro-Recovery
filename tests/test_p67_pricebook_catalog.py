from core.estimate.iran_pricebook_catalog_v1 import *
def s(y): return PricebookSource("ابنیه",y,f"فهرست بهای واحد پایه رشته ابنیه سال {y}","public-source","PDF","2026-10-04")
def test_years(): assert len(fingerprint(tuple(s(y) for y in RECENT_ABNIEH_YEARS)))==64
def test_coverage(): assert coverage(tuple(s(y) for y in RECENT_ABNIEH_YEARS))["recent_catalog_complete"]
def test_duplicate():
    try: validate((s(1404),s(1404)))
    except ValueError: return
    assert False
def test_wrong_discipline():
    x=s(1404); x=PricebookSource("راه",x.year,x.title,x.source,x.format,x.verified_at)
    try: validate((x,))
    except ValueError: return
    assert False
