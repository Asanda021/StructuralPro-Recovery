"""Source-pinned independent IFC4 landscaping selection in original Qt UI.

Targets actual IfcGeographicElement members, not a site container, generic proxy,
owner claim, made-up source, or merely successful IFC parsing.
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, tempfile, os
import ifcopenshell
from scripts.diagnostics.p6_g2_independent_site_renovation_discovery import SOURCES, obtain
from scripts.diagnostics.p6_g2_heating_sanitary_original_ui import examine
from scripts.diagnostics.p6_independent_ifc_public_reference import save_json

SITE_SOURCES = [s for s in SOURCES if s["kind"]=="site_interop_example"]
TARGET = "IfcGeographicElement"

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    summary={"status":"RUNNING","scope":"INDEPENDENT_PUBLISHED_INTEROPERABILITY_EXAMPLES_NOT_REAL_AS_BUILT_SITE",
        "head":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "original_sources_not_redistributed":True,"no_engineering_quantity_authority":True,
        "category_claim":"IFC4_LANDSCAPING_VISUAL_READONLY_ONLY","cases":[]}
    save_json(out/"summary.json",summary)
    with tempfile.TemporaryDirectory(prefix="structuralpro-p6-ifc-site-") as td:
        tmp=pathlib.Path(td)
        for spec in SITE_SOURCES:
            row={"model":spec["id"],"status":"NOT_ACCEPTED",
                 "pinned_upstream":"BIMvoice/ifcsamples@7a7eb6bdeab3e630eeef0e923a908d0c6af07cd2",
                 "independent_real_building":False}
            summary["cases"].append(row)
            try:
                path=tmp/(spec["id"]+".ifc")
                sha,length=obtain(spec,path)
                row.update(pinned_source_sha_verified=True,sha256=sha,bytes=length)
                model=ifcopenshell.open(str(path))
                member=[x for x in model.by_type(TARGET) if getattr(x,"Representation",None)]
                row.update(schema=str(model.schema),geographic_members_with_geometry=len(member),
                           total_elements=len(model.by_type("IfcElement")),
                           without_geometry=sum(not bool(x.Representation) for x in model.by_type("IfcElement")))
                if str(model.schema)!="IFC4" or len(member)<2:
                    raise ValueError("NO_TWO_REAL_GEOGRAPHIC_MEMBERS")
                detail=tmp/(spec["id"]+".json")
                rc=examine(path,sha,spec["id"],detail,preferred_target_type=TARGET)
                row.update(json.loads(detail.read_text(encoding="utf-8")))
                row["original_gui_exit"]=rc
                if (rc!=0 or row.get("status")!="PASS_TWO_REAL_BATCHES_IN_ORIGINAL_QT_UI"
                    or row.get("required_target_type_verified") is not True or row.get("boq_written") is not False):
                    row["status"]="BLOCKED_SOURCE_OR_ORIGINAL_GUI"
            except Exception as exc:
                row.update(status="BLOCKED_SOURCE_OR_ORIGINAL_GUI",exception_class=type(exc).__name__)
            save_json(out/"summary.json",summary)
            print(json.dumps({"id":spec["id"],"status":row["status"],
                              "geographic_members":row.get("geographic_members_with_geometry"),
                              "stage":row.get("failed_stage")}),flush=True)
    summary["status"]="PASS_IFC4_PUBLISHED_SITE_UI_VISUAL_SOURCE_CLASS" if (
        len(summary["cases"])==2 and
        all(x["status"]=="PASS_TWO_REAL_BATCHES_IN_ORIGINAL_QT_UI" for x in summary["cases"])
    ) else "BLOCKED_IFC4_SITE_GUI_SOURCE_CLASS"
    save_json(out/"summary.json",summary)
    return 0 if summary["status"].startswith("PASS_") else 1

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=pathlib.Path,required=True)
    raise SystemExit(run(p.parse_args().output))
