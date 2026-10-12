"""Phase 18 acceptance tests."""
from core.drawing.pdf_takeoff_workbench import PDFTakeoffWorkbench

def test_full_measurement_surface_and_sheet_management():
    w=PDFTakeoffWorkbench(); w.set_scale(.01,"PDF-01")
    w.add_sheet(1,"Foundation"); w.add_sheet(2,"Roof")
    for k,u,v in [("length","m",12),("area","m2",40),("volume","m3",8),("count","عدد",6)]:
        w.add_measurement(k,v,u,1)
    assert len(w.sheets)==2 and len(w.measurements)==4
    assert w.export()["scale"]=={"value":.01,"source":"PDF-01"}

def test_markup_crop_cutout_and_history():
    w=PDFTakeoffWorkbench(); w.add_sheet(1)
    w.add_markup("note",1,{"text":"check dimension"})
    w.add_crop(1,(0,0,100,200)); w.add_cutout(1,[(0,0),(10,0),(10,10)])
    assert w.history()["undo_available"]==4
    assert w.undo() is True and len(w.cutouts)==0
    assert w.redo() is True and len(w.cutouts)==1

def test_measurement_edit_surface_is_reversible():
    w=PDFTakeoffWorkbench(); m=w.add_measurement("length",10,"m",1)
    assert w.remove_measurement(m["id"]) is True
    assert not w.measurements
    assert w.undo() is True and len(w.measurements)==1
    assert w.redo() is True and not w.measurements

def test_invalid_inputs_fail_closed():
    w=PDFTakeoffWorkbench()
    for bad in [(0,"x"),(-1,"x")]:
        try: w.set_scale(*bad)
        except ValueError: pass
        else: assert False
    try: w.add_measurement("angle",1,"deg",1)
    except ValueError: pass
    else: assert False
