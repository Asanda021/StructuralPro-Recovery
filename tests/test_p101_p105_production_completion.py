from decimal import Decimal
from core.validation.production_benchmark_gate_v2 import evaluate
from core.cloud.production_smoke_v1 import smoke_event
from core.product.production_e2e_v1 import run
from core.windows.production_smoke_v1 import verify_windows_artifacts
from core.windows.product_v3 import WindowsRelease,WindowsWorkspace
import hashlib
def test_p102_benchmark_gate_green2():
    cases=tuple(type("C",(),{"reference_quantity":x,"system_quantity":x,"case_id":str(i),"item_id":str(i),"unit":"m3","source_ref":"fixture"})() for i,x in enumerate((10,20,30,40)))
    assert evaluate(cases)["green2"]
def test_p104_cloud_smoke():
    r=smoke_event(); assert r["accepted"]["accepted"] and r["conflict"]["conflict"]
def test_p105_full_e2e():
    class R:
        year=1404; discipline="ابنیه"; item_code="1001"; description="Concrete"; unit="m3"; unit_price=1000; source_sha256="a"*64; source_file="fixture.xlsx"
    r=run([{"takeoff_id":"Q1","discipline":"ابنیه","item_code":"1001","unit":"m3","quantity":2}],[R()],1404,"P1","R1")
    assert r["total"]==Decimal("2000") and r["report"]["rtl"]
def test_p103_windows_artifact_smoke(tmp_path):
    i=tmp_path/"setup.exe"; e=tmp_path/"StructuralPro.exe"; i.write_bytes(b"installer"); e.write_bytes(b"exe")
    release=WindowsRelease("1.0.0",str(i),str(e),hashlib.sha256(b"installer").hexdigest(),"x64","stable","Windows 10")
    assert verify_windows_artifacts(release,WindowsWorkspace(".sp",".bak",30,True,True))["valid"]
