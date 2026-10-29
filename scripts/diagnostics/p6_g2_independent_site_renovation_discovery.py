"""G2 discovery of independent published IFC4 site/renovation input candidates.

Never calls a synthetic model an independent building. Source files remain in
temporary directories; artifact contains only schema, counts, file digests,
bounded contract result and categorized error codes, never model text/geometry.
"""
from __future__ import annotations
from collections import Counter
import hashlib, json, os, pathlib, sys, tempfile, traceback, urllib.request
from core.drawings.viewer_model import DrawingViewerModel
from core.drawings.bim_adapter import BIMAdapter

BIMVOICE_SHA = "7a7eb6bdeab3e630eeef0e923a908d0c6af07cd2"
SOURCES = [
    dict(id="site_landscape", kind="site_interop_example",
         url="https://raw.githubusercontent.com/BIMvoice/ifcsamples/"+BIMVOICE_SHA+
             "/IFC4/buildingSMART-Certification-datasets/Simple-Scene/Building-Landscaping.ifc",
         size=1074044, blob="fd0a9aaa9343e7b164081edfcb1f77e6359e54fa",
         provenance="buildingSMART certification sample as redistributed by BIMvoice/ifcsamples; CC-BY-4.0"),
    dict(id="infra_landscape",kind="site_interop_example",
         url="https://raw.githubusercontent.com/BIMvoice/ifcsamples/"+BIMVOICE_SHA+
             "/IFC4/buildingSMART-Certification-datasets/Simple-Scene/Infra-Landscaping.ifc",
         size=2349038, blob="e29a81536698cd4b024c8b85b5e7eb9b445228b8",
         provenance="buildingSMART certification sample as redistributed by BIMvoice/ifcsamples; CC-BY-4.0"),
    dict(id="existing_fin",kind="renovation_existing_building_demonstrator",
         url="https://zenodo.org/records/6685810/files/BIM4EEB_DEMONSTRATION_BLDG_FIN.ifc?download=1",
         md5="10057fcf4fbbb92c34a46ceecbaa3574",
         provenance="BIM4EEB EU-funded building renovation demonstrator DOI 10.5281/zenodo.6685810"),
    dict(id="existing_pol",kind="renovation_existing_building_demonstrator",
         url="https://zenodo.org/records/6685810/files/BIM4EEB_DEMONSTRATION_BLDG_POL.ifc?download=1",
         md5="a68daae380a352dbc9d31cb2501f3891",
         provenance="BIM4EEB EU-funded building renovation demonstrator DOI 10.5281/zenodo.6685810"),
    dict(id="existing_ita",kind="renovation_existing_building_demonstrator",
         url="https://zenodo.org/records/6685810/files/BIM4EEB_DEMONSTRATION_BLDG_ITA.ifc?download=1",
         md5="2b653f05e8fd5819cf803ece82329a5d",
         provenance="BIM4EEB EU-funded building renovation demonstrator DOI 10.5281/zenodo.6685810"),
]
LIMIT=16*1024*1024


def obtain(config,path):
    req=urllib.request.Request(config["url"],headers={"User-Agent":"StructuralPro-P6-G2-Independent-Public-Source-20261029/1.0"})
    raw=b""
    with urllib.request.urlopen(req,timeout=85) as response:
        if response.status!=200: raise ValueError("HTTP_STATUS_NOT_200")
        while 1:
            b=response.read(1024*1024)
            if not b:break
            raw+=b
            if len(raw)>LIMIT:raise ValueError("DOWNLOAD_TOO_LARGE")
    if not raw.startswith(b"ISO-10303-21;"):raise ValueError("NOT_ORIGINAL_IFC_STEP")
    if "size" in config and len(raw)!=config["size"]:raise ValueError("PINNED_SOURCE_LENGTH_CHANGED")
    if "blob" in config and hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()!=config["blob"]:
        raise ValueError("PINNED_SOURCE_GIT_BLOB_CHANGED")
    if "md5" in config and hashlib.md5(raw).hexdigest()!=config["md5"]:
        raise ValueError("PINNED_SOURCE_MD5_CHANGED")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(),len(raw)

def inspect(config,root):
    result={"id":config["id"],"kind":config["kind"],"provenance":config["provenance"],
            "status":"NOT_ACCEPTED","source_pinned":False}
    f=root/(config["id"]+".ifc")
    stage="DOWNLOAD"
    try:
        sha,size=obtain(config,f)
        result.update(source_pinned=True,sha256=sha,byte_count=size)
        import ifcopenshell
        stage="PARSE_IFC"
        model=ifcopenshell.open(str(f))
        elements=model.by_type("IfcElement")
        identities=[x.GlobalId for x in elements]
        represented=[x for x in elements if getattr(x,"Representation",None)]
        result.update(schema=str(model.schema),elements=len(elements),
            represented=len(represented),unrepresented=len(elements)-len(represented),
            category_classes=dict(Counter(x.is_a() for x in elements)),
            represented_classes=dict(Counter(x.is_a() for x in represented)),
            distinct_global_ids=len(set(identities)))
        if str(model.schema)!="IFC4":raise ValueError("SCHEMA_NOT_IFC4")
        if not elements or len(set(identities))!=len(elements):raise ValueError("SOURCE_CENSUS_INVALID")
        stage="BIM_ADAPTER"
        document=BIMAdapter().read_document(f,revision="G2-PINNED")
        result["canonical_elements"]=len(document["elements"])
        stage="DISPLAY_PREVIEW"
        preview=DrawingViewerModel().open(f)
        doc=preview.ifc_document
        if preview.kind!="ifc" or not doc:raise ValueError("PREVIEW_NOT_IFC")
        result.update(preview_meshes=len(doc.meshes),
            preview_catalog_members=len(doc.source_roster),
            preview_sha256_valid=doc.source_sha256==sha)
        if doc.source_sha256!=sha or len(doc.source_roster)!=len(elements):
            raise ValueError("SOURCE_ROSTER_OR_SHA_MISMATCH")
        result["status"]="READY_FOR_ORIGINAL_GUI_CROSS_OS"
    except Exception as exc:
        frames=traceback.extract_tb(exc.__traceback__)
        last=frames[-1] if frames else None
        result.update(status="BLOCKED_SOURCE_OR_CONTRACT",failure_stage=stage,
                      error_type=type(exc).__name__,
                      last_module=pathlib.Path(last.filename).name if last else None,
                      last_line=last.lineno if last else None)
    return result

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--out",required=True,type=pathlib.Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="sp-g2-published-") as td:
        cases=[inspect(x,pathlib.Path(td)) for x in SOURCES]
    result={"source_commit":os.popen("git rev-parse HEAD").read().strip(),
            "public_originals_not_redistributed":True,"no_boq_authority":True,
            "cases":cases,"status":"SOURCE_DISCOVERY_EVIDENCE_ONLY"}
    (a.out/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    for x in cases:print(json.dumps({"id":x["id"],"status":x["status"],
            "schema":x.get("schema"),"elements":x.get("elements"),
            "represented":x.get("represented"),
            "stage":x.get("failure_stage")}),flush=True)
    return 0

if __name__=="__main__":raise SystemExit(main())
