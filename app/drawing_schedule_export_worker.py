"""Owned Qt schedule export jobs with main-thread version-gated publication."""
from __future__ import annotations

from copy import deepcopy
from threading import Event
import weakref

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import isValid

from core.reports.drawing_schedule_report import (
    prepare_drawing_schedule_bundle, publish_prepared_schedule_bundle,
    ScheduleExportCancelled,
)


class _ScheduleExportJob(QThread):
    progress = Signal(str)

    def __init__(self, snapshot, destination):
        super().__init__()
        self.snapshot=deepcopy(snapshot)
        self.destination=destination
        self.cancel_event=Event()
        self.prepared=None
        self.error=""

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            self.prepared=prepare_drawing_schedule_bundle(
                self.snapshot,self.destination,cancel_event=self.cancel_event,
                progress=self.progress.emit)
        except ScheduleExportCancelled:
            self.cancel_event.set()
        except Exception as exc:
            # ReportLab/exporter exceptions are not all ValueError/RuntimeError.
            # Preserve the concrete failure for the user; no bundle is accepted.
            self.error=type(exc).__name__+": "+str(exc)


class _ScheduleExportController(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.jobs={}
        app.aboutToQuit.connect(self._shutdown)

    @property
    def active_count(self):
        return len(self.jobs)

    def start(self, dialog, snapshot, destination):
        job=_ScheduleExportJob(snapshot,destination)
        self.jobs[job]=weakref.ref(dialog)
        # The application owns the job through this controller. Destroying a
        # dialog cancels its job without destroying a running native QThread.
        dialog.destroyed.connect(job.cancel)
        job.progress.connect(dialog._export_progress)
        job.finished.connect(self._finished)
        job.start()
        return job

    @Slot()
    def _finished(self):
        job=self.sender()
        reference=self.jobs.pop(job,None)
        dialog=reference() if reference is not None else None
        live=dialog is not None and isValid(dialog)
        try:
            if not live or job.cancel_event.is_set():
                if live:dialog.note.setText("ساخت خروجی لغو شد؛ هیچ بسته‌ای ثبت نشد")
                return
            if job.error:
                QMessageBox.warning(dialog,"خروجی زمان‌بندی ساخته نشد",job.error)
                return
            result=publish_prepared_schedule_bundle(job.prepared,dialog.get_plan())
            dialog.note.setText("خروجی PDF و Excel و گانت پیش‌نویس ذخیره شد: "+result["destination"]
                +"؛ این خروجی به معنی تأیید تاریخ تحویل یا مقادیر نیست")
        except Exception as exc:
            if live:QMessageBox.warning(dialog,"خروجی زمان‌بندی ساخته نشد",str(exc))
        finally:
            if job.prepared is not None:job.prepared.discard()
            if live:
                dialog._schedule_export_worker=None
                dialog.export_bundle_button.setEnabled(True)
                dialog.cancel_export_button.hide()
            job.deleteLater()

    @Slot()
    def _shutdown(self):
        # Cancel at a writer checkpoint, then join before Qt destroys threads.
        # No GUI objects or project databases are accessed from worker code.
        for job in self.jobs:job.cancel()
        for job in self.jobs:
            job.wait()
            if job.prepared is not None:job.prepared.discard()
            job.deleteLater()
        self.jobs.clear()


def schedule_export_controller():
    app=QApplication.instance()
    if app is None:
        raise RuntimeError("خروجی پنجره زمان‌بندی به برنامه Qt فعال نیاز دارد")
    controller=getattr(app,"_drawing_schedule_export_controller",None)
    if controller is None or not isValid(controller):
        controller=_ScheduleExportController(app)
        app._drawing_schedule_export_controller=controller
    return controller
