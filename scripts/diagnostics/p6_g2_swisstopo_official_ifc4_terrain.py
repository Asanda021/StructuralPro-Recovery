"""G2 independent official swisstopo 2024 terrain IFC4 dataset discovery.

Read publisher ZIP in a temporary path only; don't copy proprietary raw model to
CI artifacts. Do not identify IfcSite as an IfcElement or invent georeferencing.
"""
from __future__ import annotations
import io,zipfile,hashlib,json,pathlib,tempfile,urllib.request,subprocess,traceback
from collections import Counter
import ifcopenshell
from core.drawings.bim_adapter import BIMAdapter
from core.drawings.viewer_model import DrawingViewerModel

URL="https://www.swisstopo.admin.ch/dam/en/sd-web/ER8gvStgSDF4/Sample-IFC-DE.zip"

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--output",type=pathlib.Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    state={"publisher":"Swiss Federal Office of Topography (swisstopo)",
        "reference":"https://www.swisstopo.admin.ch/en/buildings-terrain-ifc",
        "published_sample":"2024-01-12","result":"PROBE_ONLY","no_redistribution":True,
        "files":[],"versioned_source_not_yet_pinned":True,
        "source_head":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()}
    try:
        request=urllib.request.Request(URL,headers={"User-Agent":"StructuralPro-G2-Published-IFC4-Terrain/1.0"})
        with urllib.request.urlopen(request,timeout=45) as response:
            if response.status!=200:raise ValueError("HTTP_STATUS_UNEXPECTED")
            raw=response.read(3*1024*1024+1)
        if len(raw)>3*1024*1024:raise ValueError("ZIP_LIMIT")
        state["zip_sha256"]=hashlib.sha256(raw).hexdigest()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries=[x for x in archive.infolist() if x.filename.lower().endswith(".ifc")]
            if not entries or len(entries)>16:raise ValueError("ZIP_IFC_ENTRY_COUNT")
            with tempfile.TemporaryDirectory(prefix="structuralpro-swisstopo-") as folder:
                for number,entry in enumerate(entries):
                    row={"index":number,"status":"PROBE_ONLY","source_size":entry.file_size}
                    state["files"].append(row)
                    try:
                        if entry.file_size>30*1024*1024:raise ValueError("IFC_SIZE_LIMIT")
                        b=archive.read(entry)
                        if len(b)!=entry.file_size or not b.startswith(b"ISO-10303-21;"):
                            raise ValueError("NOT_IFC_STEP")
                        row["sha256"]=hashlib.sha256(b).hexdigest()
                        path=pathlib.Path(folder)/f"sample-{number}.ifc"
                        path.write_bytes(b)
                        model=ifcopenshell.open(str(path))
                        es=model.by_type("IfcElement")
                        row.update(schema=str(model.schema),source_elements=len(es),
                            represented_source_members=sum(bool(getattr(x,"Representation",None)) for x in es),
                            geographic_elements=len(model.by_type("IfcGeographicElement")) if model.schema=="IFC4" else None,
                            terrain_context_site_count=len(model.by_type("IfcSite")),
                            classes=dict(Counter(x.is_a() for x in es)))
                        if model.schema=="IFC4" and es:
                            doc=BIMAdapter().read_document(path,revision="SWISSTOPO-PUBLISHED")
                            row["contract_member_count"]=len(doc["elements"])
                            preview=DrawingViewerModel().open(path)
                            row.update(preview_member_count=len(preview.ifc_document.meshes),
                                source_roster_count=len(preview.ifc_document.source_roster),
                                source_sha_verified=preview.ifc_document.source_sha256==row["sha256"])
                        row["status"]="INSPECTED"
                    except Exception as exc:
                        frames=traceback.extract_tb(exc.__traceback__)
                        row.update(status="NOT_SUPPORTED_OR_BLOCKED",error_class=type(exc).__name__,
                                   stage_module=pathlib.Path(frames[-1].filename).name if frames else None,
                                   stage_line=frames[-1].lineno if frames else None)
        state["result"]="DISCOVERY_COMPLETE_NOT_G2_ACCEPTANCE"
    except Exception as exc:
        state.update(result="OFFICIAL_SOURCE_DOWNLOAD_OR_ZIP_BLOCKED",error_class=type(exc).__name__)
    (args.output/"summary.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    print(json.dumps({"result":state["result"],"files":[{"schema":x.get("schema"),"elements":x.get("source_elements"),"status":x["status"]} for x in state["files"]]}),flush=True)
    return 0

if __name__=="__main__":raise SystemExit(main())
