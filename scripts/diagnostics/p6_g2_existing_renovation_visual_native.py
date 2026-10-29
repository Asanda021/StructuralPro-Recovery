"""Original native Qt verification with authentic EU renovation demonstrator IFC2X3.

Only visual reference, not a new engineering IFC4 authorization and not
evidence of actual demolition/construction phases or structural soundness.
"""
from __future__ import annotations
import hashlib, json, pathlib, sys, tempfile, time, urllib.request
import ifcopenshell

CASES={
 "fin":{"name":"BIM4EEB_DEMONSTRATION_BLDG_FIN.ifc","md5":"10057fcf4fbbb92c34a46ceecbaa3574",
        "elements":939,"represented":939},
 "pol":{"name":"BIM4EEB_DEMONSTRATION_BLDG_POL.ifc","md5":"a68daae380a352dbc9d31cb2501f3891",
        "elements":362,"represented":356},
}
def run(output):
    from PySide6.QtWidgets import QApplication,QFileDialog
    from app.graphical_takeoff import GraphicalTakeoffDialog
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    data={"source":"BIM4EEB EU renovation existing-building demonstrator, Zenodo DOI 10.5281/zenodo.6685810",
          "source_not_redistributed":True,"schema_scope":"IFC2X3 VISUAL ONLY",
          "engineering_ifc4_schema_unchanged":True,
          "renovation_interventions_or_phases_verified":False,
          "cases":rows,"status":"RUNNING"}
    def save(): (output/"summary.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    save()
    app=QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="sp-g2-renovation-reference-") as td:
        for key,spec in CASES.items():
            row={"id":key,"status":"FAIL","expected_elements":spec["elements"]}
            rows.append(row);save()
            path=pathlib.Path(td)/(key+".ifc");win=None
            prev_picker=QFileDialog.getOpenFileName
            try:
                url="https://zenodo.org/records/6685810/files/"+spec["name"]+"?download=1"
                with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"StructuralPro-P6-G2-BIM4EEB/1.0"}),timeout=95) as r:
                    raw=r.read(12*1024*1024+1)
                if len(raw)>12*1024*1024 or hashlib.md5(raw).hexdigest()!=spec["md5"]:
                    raise ValueError("SOURCE_MD5_OR_SIZE_MISMATCH")
                sha=hashlib.sha256(raw).hexdigest()
                path.write_bytes(raw)
                model=ifcopenshell.open(str(path))
                elems=model.by_type("IfcElement")
                represented=sum(bool(getattr(x,"Representation",None)) for x in elems)
                row.update(schema=str(model.schema),source_members=len(elems),
                           represented=represented,source_sha256=sha,
                           publisher_md5_verified=True)
                if str(model.schema)!="IFC2X3" or len(elems)!=spec["elements"] or represented!=spec["represented"]:
                    raise ValueError("PINNED_ORIGINAL_SOURCE_CENSUS_CHANGED")
                win=GraphicalTakeoffDialog()
                win.ifc_revision.setText("BIM4EEB-SOURCE-2026")
                before_items=list(win.session.items)
                QFileDialog.getOpenFileName=lambda *args,**kwargs:(str(path),"IFC (*.ifc)")
                win.existing_reference_button.click()
                end=time.monotonic()+95
                while win._existing_reference_job is not None and time.monotonic()<end:
                    app.processEvents();time.sleep(.025)
                app.processEvents()
                dialog=win._existing_reference_dialog
                if dialog is None:
                    raise ValueError("ORIGINAL_EXISTING_BUILDING_QT_WINDOW_NOT_OPEN")
                scene=dialog.scene;scene.validate_source()
                if (scene.source_sha256!=sha or
                    scene.source_member_count!=len(elems) or
                    scene.source_with_geometry_count!=represented or
                    scene.display_kind!="IFC2X3-existing-building-visual-only" or
                    scene.element_global_ids!=frozenset() or
                    scene.member_identity_linkable is not False or
                    scene.quantity_authority is not False or
                    scene.renovation_phases_verified is not False or
                    hasattr(scene,"pick") or
                    not scene.projected_triangles(700,500) or
                    list(win.session.items)!=before_items):
                    raise ValueError("NO_BOQ_OR_SOURCE_SCENE_CONTRACT_FAILED")
                path.write_bytes(raw+b"\n/* modified during acceptance */")
                try:scene.validate_source()
                except ValueError:pass
                else:raise ValueError("REPLACED_REFERENCE_NOT_REVOKED")
                dialog.canvas.check_source()
                if not dialog.canvas.source_error or list(win.session.items)!=before_items:
                    raise ValueError("STALE_REFERENCE_UI_NOT_CLEARED")
                row.update(status="PASS_REAL_EXISTING_BUILDING_READONLY_NATIVE_GUI",
                           displayed_source_member_count=1,
                           triangles=len(scene.triangles),source_mutation_rejected=True,
                           boq_unchanged=True,quantity_authority=False)
            except Exception as exc:
                row["status"]="BLOCKED_SOURCE_OR_ORIGINAL_GUI"
                row["error_type"]=type(exc).__name__
                reason=str(exc)
                row["category"]=reason if reason.isupper() and len(reason)<100 else "MODEL_OR_NATIVE_UI_REJECTED"
                if win is not None:row["qt_status_category"]="WORKER_REJECTED" if "رد شد" in win.status.text() else "OTHER"
            finally:
                QFileDialog.getOpenFileName=prev_picker
                if win is not None:
                    try:
                        if win._existing_reference_dialog:win._existing_reference_dialog.close()
                        win.close();app.processEvents()
                    except Exception:pass
            save()
            print(json.dumps({"id":key,"status":row["status"],"triangles":row.get("triangles"),
                              "reason":row.get("category")}),flush=True)
    data["status"]="PASS_TWO_REAL_RENOVATION_ASBUILT_VISUAL_ONLY" if (
        len(rows)==len(CASES) and all(x["status"]=="PASS_REAL_EXISTING_BUILDING_READONLY_NATIVE_GUI" for x in rows)
    ) else "BLOCKED_REAL_RENOVATION_ASBUILT_VISUAL_ONLY"
    save()
    return 0 if data["status"].startswith("PASS_") else 1

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--output",type=pathlib.Path,required=True)
    raise SystemExit(run(p.parse_args().output))
