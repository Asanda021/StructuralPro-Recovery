import tempfile
from pathlib import Path
import json
from core.validation.gate import *

def test_pdf_dxf_ifc_reference_formats():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        import fitz
        pdf=root/"project.pdf"; doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),"GOLDEN PROJECT"); doc.save(pdf); doc.close()
        assert validate_pdf(pdf).passed
        import ezdxf
        dxf=root/"project.dxf"; drawing=ezdxf.new("R2010"); drawing.modelspace().add_line((0,0),(10,0)); drawing.saveas(dxf)
        assert validate_dxf(dxf).passed
        ifc=root/"project.ifc"; ifc.write_text("ISO-10303-21;\n#1=IFCPROJECT('0');\nEND-ISO-10303-21;\n",encoding="utf-8")
        assert validate_ifc(ifc).passed

def test_golden_quantities_and_boq_are_deterministic():
    from core.takeoff.construction_core import ConstructionQuantityCore
    from core.takeoff.element_model import ConstructionElement
    from core.takeoff.estimate import build_estimate
    element=ConstructionElement(id="G1",kind="column",length_m=2,width_m=0.3,height_m=0.3,quantity_count=10,source_id="golden:G1")
    line=ConstructionQuantityCore.rectangular_volume(element)
    assert abs(line.quantity-1.8)<1e-12 and line.unit=="m3"
    estimate=build_estimate([line],aggregate=True)
    assert estimate["finalizable"] and estimate["boq"]

def test_security_and_path_traversal_fail_closed():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); assert security_path_gate(root,root/"safe.json").passed
        assert not security_path_gate(root,root/".." / "escape.json").passed
    assert not security_payload_gate({"bot_token":"abc","nested":{"api_key":"x"}}).passed
    assert security_payload_gate({"project":"safe","quantity":10}).passed

def test_recovery_round_trip_and_fingerprint():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"backup.json"; payload={"id":"P1","boq":[{"item":"CON","q":1.8}]}
        r=recovery_round_trip(payload,p)
        assert r.passed and r.evidence and json.loads(p.read_text())==payload

def test_performance_budget_and_expert_gate():
    r=measure_performance(lambda: sum(range(20)),iterations=500,max_seconds=5)
    assert r.passed
    assert expert_gate([ExpertReview("ENG-01","G1",True,"approved")],{"G1"}).passed
    assert not expert_gate([],{"G1"}).passed

def test_validation_summary_fails_closed():
    s=validation_summary([ValidationResult("a",True),ValidationResult("b",False)])
    assert not s["ready"] and s["failed_cases"]==["b"]
