"""Native Windows/Linux acceptance: official Swiss IFC4 IfcSite-only terrain in Qt.

Original swisstopo ZIP, pinned digest and member hashes. Source not republished;
site context is never treated as IfcElement, no QTO/BOQ code is invoked.
"""
from __future__ import annotations
import hashlib, io, json, pathlib, sys, tempfile, time, urllib.request, zipfile

ZIP_SHA = "6e2a370ca56a0a09e4baf52cbe008a88d9f39b97dc1e0bf66c8073d445f3d189"
ZIP_URL = "https://www.swisstopo.admin.ch/dam/en/sd-web/ER8gvStgSDF4/Sample-IFC-DE.zip"
IFC_SHA = (
    "eefe0462eab545b893f610163be26781dd560f770179789cc3ee4c7ca8f37407",
    "885e84743667d3e39a86ba430717ba203c3bb330161d68719f12624e313c09fd",
)

def main():
    import argparse
    from PySide6.QtWidgets import QApplication, QFileDialog
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.drawings.site_context import verified_site_context
    p=argparse.ArgumentParser();p.add_argument("--output",required=True,type=pathlib.Path)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    summary={"status":"RUNNING","source":"Swiss Federal Office of Topography, 2024 IFC4 terrain sample",
             "source_original_zip_sha256":ZIP_SHA,"not_redistributed":True,"results":rows}
    def save():
        (args.output/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    save()
    with urllib.request.urlopen(urllib.request.Request(ZIP_URL,headers={"User-Agent":"StructuralPro-G2-TerrainAcceptance/1.0"}), timeout=90) as r:
        payload=r.read(3*1024*1024+1)
    if hashlib.sha256(payload).hexdigest()!=ZIP_SHA:
        summary["status"]="FAIL_SOURCE_ZIP_PIN";save();return 1
    app=QApplication.instance() or QApplication([])
    with zipfile.ZipFile(io.BytesIO(payload)) as archive, tempfile.TemporaryDirectory(prefix="p6-swiss-ifc-") as d:
        members=[m for m in archive.infolist() if m.filename.lower().endswith(".ifc")]
        if len(members)<2:
            summary["status"]="FAIL_ARCHIVE_CONTENTS";save();return 1
        for i,expected in enumerate(IFC_SHA):
            row={"index":i,"status":"FAIL","element_count":None}
            rows.append(row);save()
            raw=archive.read(members[i])
            if hashlib.sha256(raw).hexdigest()!=expected:
                row["error"]="PINNED_IFC_DIGEST";save();continue
            source=pathlib.Path(d)/("site-"+str(i)+".ifc")
            source.write_bytes(raw)
            mainwin=None
            old_picker=QFileDialog.getOpenFileName
            try:
                import ifcopenshell
                model=ifcopenshell.open(str(source))
                row["element_count"]=len(model.by_type("IfcElement"))
                row["site_count"]=len(model.by_type("IfcSite"))
                if row["element_count"]!=0 or row["site_count"]!=1:
                    raise ValueError("NOT_SITE_ONLY_IFC")
                mainwin=GraphicalTakeoffDialog()
                mainwin.ifc_revision.setText("SWISS-G2-REAL-SITE-2026")
                snapshot=list(mainwin.session.items)
                QFileDialog.getOpenFileName=lambda *args,**kwargs:(str(source),"IFC4 (*.ifc)")
                if not mainwin.site_context_button.click() is None:
                    raise ValueError("BUTTON_CLICK_FAILURE")
                deadline=time.monotonic()+85
                while mainwin._site_context_loader is not None and time.monotonic()<deadline:
                    app.processEvents()
                    time.sleep(.02)
                app.processEvents()
                view=mainwin._site_context_dialog
                if view is None or view.scene.source_sha256!=expected:
                    raise ValueError("ORIGINAL_QT_SITE_WINDOW_NOT_OPEN")
                terrain=view.scene
                terrain.validate_source()
                if (terrain.display_kind!="IfcSite-spatial-only" or
                    terrain.element_global_ids!=frozenset() or
                    terrain.quantity_authority is not False or
                    hasattr(terrain,"meshes") or hasattr(terrain,"pick") or
                    not terrain.projected_triangles(850,550) or
                    list(mainwin.session.items)!=snapshot):
                    raise ValueError("SPATIAL_ONLY_SAFETY_CONTRACT")
                terrain.orbit(.12,.1)
                terrain.pan(4,5)
                terrain.set_zoom(1.2)
                if not terrain.projected_triangles(850,550):
                    raise ValueError("SITE_ORBIT_NO_FACES")
                source.write_bytes(raw+b"\n/* modified in test */")
                try:
                    terrain.validate_source()
                except ValueError:
                    pass
                else:
                    raise ValueError("SOURCE_MUTATION_NOT_REVOKED")
                view.canvas.check_source()
                if not view.canvas.source_error or list(mainwin.session.items)!=snapshot:
                    raise ValueError("STALE_SOURCE_UI_NOT_REVOKED")
                row.update(status="PASS_NATIVE_SITE_ONLY_GUI",faces=len(terrain.triangles),
                           source_sha256=expected,boq_unchanged=True,
                           source_mutation_rejected=True,revision=terrain.revision,
                           quantity_authority=False)
            except Exception as exc:
                row.update(status="FAIL",error_class=type(exc).__name__,
                           error_category=str(exc) if str(exc).isupper() and len(str(exc))<80 else "MODEL_OR_UI_REJECTED")
                row["status_kind"] = (
                    "QT_MODEL_REJECTED" if mainwin and "رد شد" in mainwin.status.text()
                    else "QT_LOAD_PENDING_OR_FAILED")
                try:
                    import traceback
                    direct=verified_site_context(source, revision="SITE-DIRECT-PROBE",
                                                 expected_sha256=expected)
                    row["direct_geometry"]={"status":"PASS","triangles":len(direct.triangles)}
                except Exception as direct_exc:
                    frame=traceback.extract_tb(direct_exc.__traceback__)[-1]
                    row["direct_geometry"]={"status":"BLOCKED","error_class":type(direct_exc).__name__,
                                            "module":pathlib.Path(frame.filename).name,"line":frame.lineno,
                                            "safe_category":str(direct_exc) if str(direct_exc) in (
                                                "شبکهٔ مثلثی IfcSite قابل نمایش نیست.",
                                                "مدل زمین از ظرفیت ۴۰ هزار مثلث فراتر است.",
                                                "مدل باید دقیقاً یک IfcSite دارای هندسهٔ صریح داشته باشد.",
                                                "نمای زمین فقط IFC4 با پروژهٔ یکتا را می‌پذیرد.",
                                                "واحد طول منبع زمین باید یکتا باشد.") else "SOURCE_SHAPE_OR_NATIVE")}
            finally:
                QFileDialog.getOpenFileName=old_picker
                if mainwin is not None:
                    try:
                        if mainwin._site_context_dialog:mainwin._site_context_dialog.close()
                        mainwin.close()
                        app.processEvents()
                    except Exception:
                        pass
            save()
            print(json.dumps({"index":i,"status":row["status"],"faces":row.get("faces"),
                              "reason":row.get("error_category")}),flush=True)
    summary["status"]="PASS_ORIGINAL_QT_TWO_REAL_SITE_CONTEXT_MODELS" if all(x["status"]=="PASS_NATIVE_SITE_ONLY_GUI" for x in rows) and len(rows)==2 else "BLOCKED_SITE_NATIVE_QT"
    save()
    return 0 if summary["status"].startswith("PASS_") else 1

if __name__=="__main__":raise SystemExit(main())
