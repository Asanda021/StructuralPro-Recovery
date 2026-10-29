"""Check independently published HBIM of existing historic tower with original UI.

Source: Zenodo 10.5281/zenodo.10937432. This model is existing heritage
reference, not an authenticated record of renovation phases/interventions.
No raw IFC/vertices/author fields redistributed in Actions artifacts.
"""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,subprocess,sys,tempfile,urllib.request
import ifcopenshell
from scripts.diagnostics.p6_independent_ifc_public_reference import save_json
from scripts.diagnostics.p6_g2_heating_sanitary_original_ui import examine

URL="https://zenodo.org/records/10937432/files/Rame_Tower.ifc?download=1"
PIN_MD5="8ca3c34bf7fde9f8379b07210fad96ff"
MAX_BYTES=22*1024*1024

def run(output):
    output.mkdir(parents=True,exist_ok=False)
    result={"source":"Zenodo historic HBIM Torre del Rame",
        "doi":"10.5281/zenodo.10937432",
        "existing_heritage_building":True,
        "renovation_interventions_or_phases_verified":False,
        "source_original_not_redistributed":True,
        "source_md5_from_publisher":PIN_MD5,
        "tested_head":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "status":"RUNNING"}
    save_json(output/"summary.json",result)
    with tempfile.TemporaryDirectory(prefix="p6-g2-heritage-") as td:
        file=pathlib.Path(td)/"existing_historic_tower.ifc"
        try:
            hmd5=hashlib.md5();h256=hashlib.sha256();size=0
            with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"StructuralPro-existing-HBIM-2026/1.0"}), timeout=95) as r, file.open("wb") as w:
                if r.status!=200:raise ValueError("HTTP_SOURCE_FAILURE")
                while True:
                    b=r.read(1024*1024)
                    if not b:break
                    size+=len(b)
                    if size>MAX_BYTES:raise ValueError("MAX_SOURCE_BYTES")
                    hmd5.update(b);h256.update(b);w.write(b)
            if hmd5.hexdigest()!=PIN_MD5:raise ValueError("SOURCE_MD5_MISMATCH")
            sha=h256.hexdigest();result.update(source_sha256=sha,source_bytes=size,source_md5_verified=True)
            model=ifcopenshell.open(str(file))
            rows=model.by_type("IfcElement")
            represented=[r for r in rows if getattr(r,"Representation",None)]
            result.update(schema=str(model.schema),ifc_element_count=len(rows),
                          represented_element_count=len(represented),
                          no_geometry_count=len(rows)-len(represented),
                          distinct_ifc_element_classes=len({r.is_a() for r in rows}))
            if model.schema!="IFC4":raise ValueError("UNSUPPORTED_SOURCE_SCHEMA")
            if len(represented)<2:raise ValueError("INSUFFICIENT_HERITAGE_ELEMENT_GEOMETRY")
            detail=pathlib.Path(td)/"ui-result.json"
            code=examine(file,sha,"historic_existing_heritage",detail)
            if detail.is_file():
                e=json.loads(detail.read_text(encoding="utf-8"))
                for key in ("status","source_element_count","source_represented_count",
                            "source_unrepresented_count","different_real_source_member_selected",
                            "old_pick_revoked","boq_written","source_sha256_matches",
                            "error_class","failed_stage","failure_isolation"):
                    if key in e:result["ui_"+key]=e[key]
            result["ui_child_exit_code"]=code
            result["status"]="PASS_IFC4_HERITAGE_EXISTING_BUILDING_VISUAL_READONLY" if (
                code==0 and result.get("ui_status")=="PASS_TWO_REAL_BATCHES_IN_ORIGINAL_QT_UI"
            ) else "BLOCKED_ORIGINAL_HERITAGE_GUI"
        except Exception as exc:
            result["status"]="BLOCKED_HERITAGE_SOURCE_OR_SCHEMA"
            result["error_class"]=type(exc).__name__
            result["error_category"]=str(exc) if str(exc).isupper() and len(str(exc))<100 else "SOURCE_OR_CONTRACT_REJECTED"
    save_json(output/"summary.json",result)
    print(json.dumps({"status":result["status"],"schema":result.get("schema"),
                      "elements":result.get("ifc_element_count"),
                      "ui_result":result.get("ui_status")}),flush=True)
    return 0 if result["status"].startswith("PASS_") else 1

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=pathlib.Path,required=True)
    raise SystemExit(run(p.parse_args().output))
