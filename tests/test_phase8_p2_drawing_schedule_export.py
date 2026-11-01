"""SYNTHETIC plan; real source hashes, RTL exports, staging and Qt controls."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

import pytest

from core.drawings.workflow_planning import new_workflow_plan
from core.projects.iran_worksite_calendar import make_calendar,calendarize


def plan(tmp_path):
    source=tmp_path/"identity-only-source.dxf"
    source.write_bytes(b"SYNTHETIC - identity fixture, not CAD geometry approval")
    result=new_workflow_plan(drawing_source=str(source),
        source_sha256=sha256(source.read_bytes()).hexdigest(),
        structure="unknown",disciplines=["architecture"])
    return calendarize(result,make_calendar(start_date="1405/08/09"))


def export(p,destination):
    from core.reports.drawing_schedule_report import export_drawing_schedule_bundle
    return export_drawing_schedule_bundle(p,destination)


def test_source_bound_draft_schedule_exports_real_rtl_pdf_xlsx_and_manifest(tmp_path):
    from openpyxl import load_workbook
    import pymupdf
    p=plan(tmp_path);before=deepcopy(p);dest=tmp_path/"reports"
    result=export(p,dest)
    assert p==before
    manifest=json.loads((dest/"manifest.json").read_text())
    assert manifest["status"]=="DRAFT_UNAPPROVED"
    assert manifest["source_sha256"]==p["source_sha256"]
    assert manifest["critical_path_approved"] is False
    assert manifest["quantities_approved"] is False
    assert manifest["plan_sha256"]==sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    for item in manifest["files"]:
        assert sha256((dest/item["name"]).read_bytes()).hexdigest()==item["sha256"]
    with pymupdf.open(dest/"schedule.pdf") as doc:
        assert len(doc)>=2
        assert sum(len(page.get_images()) for page in doc)>=1
    book=load_workbook(dest/"schedule.xlsx")
    assert all(sheet.sheet_view.rightToLeft for sheet in book)
    assert any("مدت" in str(cell.value) for sheet in book for row in sheet for cell in row)
    book.close()
    assert result["destination"]==str(dest)


def test_schedule_export_missing_source_or_undated_plan_leaves_no_output(tmp_path):
    p=plan(tmp_path);p.pop("calendar")
    with pytest.raises(ValueError,match="تاریخ|تقویم"):
        export(p,tmp_path/"undated")
    assert not (tmp_path/"undated").exists()
    p=plan(tmp_path);Path(p["drawing_source"]).unlink()
    with pytest.raises(ValueError,match="منبع"):
        export(p,tmp_path/"missing")
    assert not (tmp_path/"missing").exists()


def test_schedule_source_mutated_during_export_discards_every_file(tmp_path,monkeypatch):
    from core.reports.project_report import ProjectReport
    p=plan(tmp_path);real=ProjectReport.export
    def mutate(self,path,fmt):
        value=real(self,path,fmt)
        Path(p["drawing_source"]).write_bytes(b"changed source")
        return value
    monkeypatch.setattr(ProjectReport,"export",mutate)
    with pytest.raises(ValueError,match="منبع|تغییر"):
        export(p,tmp_path/"reports")
    assert not (tmp_path/"reports").exists()
    assert not list(tmp_path.glob(".structuralpro-schedule-*"))


def test_schedule_plan_mutated_during_export_is_not_published(tmp_path,monkeypatch):
    from core.reports.project_report import ProjectReport
    p=plan(tmp_path);real=ProjectReport.export
    def mutate(self,path,fmt):
        value=real(self,path,fmt)
        p["tasks"][0]["duration_days"]+=1
        return value
    monkeypatch.setattr(ProjectReport,"export",mutate)
    with pytest.raises(ValueError,match="نسخه|تغییر"):
        export(p,tmp_path/"reports")
    assert not (tmp_path/"reports").exists()


def test_schedule_export_does_not_overwrite_existing_directory(tmp_path):
    p=plan(tmp_path);dest=tmp_path/"reports";dest.mkdir()
    keep=dest/"owner.txt";keep.write_text("keep")
    with pytest.raises((ValueError,FileExistsError)):
        export(p,dest)
    assert keep.read_text()=="keep"


def test_schedule_table_and_gantt_offsets_must_agree_before_export(tmp_path):
    p=plan(tmp_path);p["tasks"][0]["start_workday_offset"]=99
    with pytest.raises(ValueError,match="زمان|برنامه|تطبیق"):
        export(p,tmp_path/"stale")
    assert not (tmp_path/"stale").exists()


def test_qt_schedule_export_button_publishes_the_current_plan(tmp_path,monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog
    from app.drawing_workflow_dialog import DrawingScheduleDialog
    app=QApplication.instance() or QApplication([])
    p=plan(tmp_path)
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",lambda *args,**kwargs:str(tmp_path))
    dialog=DrawingScheduleDialog(lambda:p,lambda value:None)
    try:
        dialog.show();app.processEvents()
        dialog.export_bundle_button.click();app.processEvents()
        assert dialog._schedule_export_worker is not None
        from time import monotonic
        deadline=monotonic()+15
        while dialog._schedule_export_worker is not None and monotonic()<deadline:
            app.processEvents()
        assert dialog._schedule_export_worker is None
        reports=list(tmp_path.glob("StructuralPro_Schedule_*"))
        assert len(reports)==1
        assert (reports[0]/"schedule.pdf").is_file()
        assert (reports[0]/"schedule.xlsx").is_file()
        assert json.loads((reports[0]/"manifest.json").read_text())["source_sha256"]==p["source_sha256"]
    finally:
        dialog.close();dialog.deleteLater();app.processEvents()


def test_many_measured_items_use_bounded_pdf_cells_with_complete_detail(tmp_path):
    import csv
    p=plan(tmp_path)
    p["tasks"][0]["measured"]={str(i):{"quantity":"123.45","unit":"m2","source_ref":f"source-{i}"} for i in range(150)}
    p["tasks"][0]["linked_item_ids"]=[str(i) for i in range(150)]
    export(p,tmp_path/"many")
    details=(tmp_path/"many"/"measurement-details.csv").read_text(encoding="utf-8-sig")
    assert all(f"source-{i}" in details for i in range(150))
    assert (tmp_path/"many"/"schedule.pdf").is_file()


@pytest.mark.parametrize("action", ["cancel", "change_plan", "delete_dialog"])
def test_qt_export_worker_keeps_event_loop_alive_and_discards_stale_bundle(tmp_path,monkeypatch,action):
    import os,threading,time
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QFileDialog
    from app.drawing_workflow_dialog import DrawingScheduleDialog
    from app import drawing_schedule_export_worker as workers
    app=QApplication.instance() or QApplication([])
    p=plan(tmp_path);entered=threading.Event();release=threading.Event()
    real=workers.prepare_drawing_schedule_bundle
    def slow(*args,**kwargs):
        entered.set()
        assert release.wait(10)
        return real(*args,**kwargs)
    monkeypatch.setattr(workers,"prepare_drawing_schedule_bundle",slow)
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",lambda *a,**kw:str(tmp_path))
    monkeypatch.setattr(workers.QMessageBox,"warning",lambda *a,**kw:None)
    dialog=DrawingScheduleDialog(lambda:p,lambda value:None)
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(1)
    try:
        begin=time.monotonic();dialog.export_bundle_button.click()
        assert time.monotonic()-begin<1
        job=dialog._schedule_export_worker
        assert job is not None
        deadline=time.monotonic()+3
        while (not entered.is_set() or len(ticks)<3) and time.monotonic()<deadline:
            app.processEvents()
        assert entered.is_set() and len(ticks)>=3
        if action=="cancel":dialog.cancel_export_button.click()
        elif action=="change_plan":p["tasks"][0]["duration_days"]+=1
        else:
            dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        release.set()
        deadline=time.monotonic()+15
        controller=workers.schedule_export_controller()
        while controller.active_count and time.monotonic()<deadline:
            app.processEvents()
        assert controller.active_count==0
        assert not list(tmp_path.glob("StructuralPro_Schedule_*"))
        assert not list(tmp_path.glob(".structuralpro-schedule-*"))
    finally:
        release.set();timer.stop()
        from shiboken6 import isValid
        if isValid(dialog):dialog.close();dialog.deleteLater()
        app.processEvents()
