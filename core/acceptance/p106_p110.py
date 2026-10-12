"""Production acceptance orchestration for P106-P110.
This layer proves repository behavior on representative concrete-building cases.
It does not claim that an external DWG/IFC engine exists when it is not installed.
"""
from __future__ import annotations
from pathlib import Path
import json
from core.engineering.deep_quantity import concrete_volume, rebar_weight, roof_concrete_volume, bar_cut_plan
from core.validation.real_data import validate_project
from core.drawings.dwg_capabilities import detect_dwg_capabilities
from core.bim.roundtrip import roundtrip_manifest, verify_manifest
from core.pipeline.production import build_production_package

def load_cases(root: str|Path) -> list[dict]:
    p=Path(root)
    cases=[json.loads(x.read_text(encoding="utf-8")) for x in sorted(p.glob("P106-*.json"))]
    if len(cases)<5: raise ValueError("P106 acceptance pack requires at least five cases")
    return cases

def run_engineering_case(case: dict) -> dict:
    c=case["geometry"]
    concrete=concrete_volume(c["length"],c["width"],c["depth"],c.get("count",1),c.get("openings",0))
    rebar=rebar_weight(case["rebar"]["length_m"],case["rebar"]["diameter_mm"],case["rebar"].get("count",1),case["rebar"].get("extra_length_m",0))
    roof=None
    if "roof" in case:
        r=case["roof"]; roof=roof_concrete_volume(r["area_m2"],r["thickness_m"],r["roof_type"])
    cuts=bar_cut_plan(case["cut_lengths_m"],12.0,case.get("waste_allowance",0))
    return {"concrete_m3":concrete,"rebar_kg":rebar,"roof_m3":roof,"stock_bars":cuts["stock_bar_count"],"cut_plan":cuts}

def run_dwg_boundary() -> dict:
    c=detect_dwg_capabilities()
    return {"native_reader":c.native_reader,"converter":c.converter,"converter_kind":c.converter_kind,
            "available":bool(c.native_reader or c.converter),"message":c.message}

def run_bim_roundtrip(model: dict) -> dict:
    manifest=roundtrip_manifest(model)
    return {"verified":verify_manifest(manifest),"digest":manifest["digest"],"schema":manifest["schema"]}

def run_e2e(case: dict) -> dict:
    result=run_engineering_case(case)
    source=case["case_id"]
    project={"id":source,"name":case["name"],
             "takeoffs":[{"id":source+"-T1","source_id":source,"description":"Concrete","quantity":result["concrete_m3"],"unit":"m3"}],
             "boq":[{"code":source+"-C","description":"Concrete","quantity":result["concrete_m3"],"unit":"m3","source":source,"unit_price":case["unit_price"],"total":result["concrete_m3"]*case["unit_price"]}],
             "estimate":{"cost":{"base":result["concrete_m3"]*case["unit_price"]}}}
    return build_production_package(takeoffs=project["takeoffs"],boq=project["boq"],estimate=project["estimate"],project_id=source)
