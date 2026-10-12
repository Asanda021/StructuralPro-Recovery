import json, tempfile
from pathlib import Path
from core.estimate.pricebook_ingestion_v1 import *
def rows(): return parse_rows([{"کد":"080106","شرح":"بتن","واحد":"مترمکعب","بهای واحد":"۱۲۳۴۵۶۷"}],1404)
def test_parse_and_fingerprint(): assert len(fingerprint(rows()))==64 and rows()[0].rate==1234567
def test_price_takeoff(): assert price_takeoff(({"item_code":"080106","unit":"مترمکعب","quantity":"2"},),rows())[0].amount==2469134
def test_missing_rate():
    try: price_takeoff(({"item_code":"999999","unit":"مترمکعب","quantity":1},),rows())
    except KeyError: return
    assert False
def test_json_loader():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"x.json"; p.write_text(json.dumps([{"item_code":"080106","description":"بتن","unit":"m3","rate":10}]),encoding="utf-8")
        assert load_json(p,1404)[0].rate==10
