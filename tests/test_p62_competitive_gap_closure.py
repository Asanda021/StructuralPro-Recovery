from core.product.full_building_takeoff_v2 import TakeoffScope, coverage_report
from core.iran.rules_v2 import IranianRule, apply_rule, import_rules, rule_fingerprint
from core.windows.product_v2 import WindowsProductContract, installer_manifest
from core.cloud.collaboration_v2 import make_envelope, resolve_sync

def test_complete_building_scope_and_missing_gate():
    rows=[TakeoffScope("architecture","A1","walls","m2",10,"draw-1"),TakeoffScope("electrical","E1","lighting","count",5,"draw-2")]
    report=coverage_report(rows,["architecture","electrical"])
    assert report["complete"] is True
    assert coverage_report(rows,["architecture","structure"])["complete"] is False

def test_iranian_rule_and_user_import_are_deterministic():
    rule=IranianRule("r1","official-source","1405","concrete","C-01","m3",1.05,3,True)
    assert apply_rule(10,rule,.1)==11.55
    payload='[{"rule_id":"r1","source":"user-import","version":"1405","discipline":"concrete","item_code":"C-01","unit":"m3","factor":1.0}]'
    imported=import_rules(payload)
    assert len(imported)==1 and len(rule_fingerprint(imported))==64

def test_windows_product_contract():
    c=WindowsProductContract("2.1.0","StructuralPro-2.1.0-Setup.exe","StructuralPro.exe",True,True,(".spx",".boq"),"stable")
    assert installer_manifest(c)["platform"]=="windows"

def test_cloud_sync_is_offline_first_and_conflicts_are_explicit():
    a=make_envelope("P1",1,"u1","base",{"qty":10},"update")
    b=make_envelope("P1",2,"u2",a.payload_fingerprint,{"qty":11},"update")
    assert resolve_sync(a,b)=="apply_remote"
    conflict=make_envelope("P1",3,"u3","different",{"qty":12},"update")
    assert resolve_sync(b,conflict)=="conflict"
