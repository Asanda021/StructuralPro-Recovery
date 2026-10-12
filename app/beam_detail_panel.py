"""Persian beam takeoff review pane for the existing graphical drawing workspace.

It does not pretend to extract rebar from CAD. Only verified measurements and
explicitly reviewed detail entries may be committed to project BOQ.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QScrollArea, QGroupBox,
)

from core.takeoff.beam_detail import BAR_TYPES, BAR_LABELS, empty_beam

_STATUS_LABELS = {
    "needs_detail": "نیازمند ورود دیتایل", "unreviewed": "بررسی‌نشده",
    "needs_review": "نیازمند تأیید", "confirmed": "تأییدشده",
    "not_applicable": "فاقد میلگرد؛ بررسی و تأیید شد",
}


class BeamDetailPanel(QWidget):
    """Editable review pane. The drawing viewer remains visible alongside it."""

    def __init__(self, service, project_id_getter, drawing_context_getter, parent=None):
        super().__init__(parent)
        self.service = service
        self.project_id_getter = project_id_getter
        self.drawing_context_getter = drawing_context_getter
        self.revision = 0
        self._loaded_identity = None
        self._segmented_kinds = set()
        self.setMinimumWidth(360)
        root = QVBoxLayout(self)
        title = QLabel("متره ترکیبی تیر — کنترل دیتایل")
        title.setStyleSheet("font-weight: 700")
        root.addWidget(title)
        hint = QLabel("ابتدا تیر و ناحیه آن را در نقشه انتخاب کنید. اطلاعات نامشخص را وارد و اقلام را جداگانه بررسی کنید.")
        hint.setWordWrap(True)
        root.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        content = QWidget()
        scroll.setWidget(content)
        column = QVBoxLayout(content)
        self.floor = QLineEdit()
        self.beam = QLineEdit()
        self.reviewer = QLineEdit()
        identity = QGroupBox("شناسه و مسئول بازبینی")
        identity_form = QFormLayout(identity)
        for label, editor in (("طبقه", self.floor), ("شناسه تیر", self.beam),
                              ("تأییدکننده", self.reviewer)):
            identity_form.addRow(label, editor)
        column.addWidget(identity)
        self.geometry = {}
        box = QGroupBox("ابعاد و بتن تیر — واحد متر")
        f = QFormLayout(box)
        for key, label in (("length", "طول"), ("width", "عرض"),
                           ("depth", "ارتفاع مقطع"), ("count", "تعداد"),
                           ("deductions_m3", "کسر هم‌پوشانی (مترمکعب)"),
                           ("source_ref", "مرجع دیتایل ابعاد")):
            editor = QLineEdit()
            self.geometry[key] = editor
            f.addRow(label, editor)
        column.addWidget(box)
        self.formwork = {}
        box = QGroupBox("قالب‌بندی — سطح خالص تأییدشده")
        f = QFormLayout(box)
        for key, label in (("net_area_m2", "مساحت خالص (مترمربع)"),
                           ("source_ref", "مرجع سطوح قالب")):
            editor = QLineEdit()
            self.formwork[key] = editor
            f.addRow(label, editor)
        column.addWidget(box)
        self.bars = {}
        for kind in BAR_TYPES:
            box = QGroupBox(BAR_LABELS[kind])
            form = QFormLayout(box)
            status = QComboBox()
            for code, label in _STATUS_LABELS.items():
                status.addItem(label, code)
            form.addRow("وضعیت بررسی", status)
            widgets = {"status": status}
            for field, label in (("count", "تعداد"), ("cut_length_m", "طول برش تأییدشده (متر)"),
                                 ("unit_weight_kg_m", "وزن واحد (کیلوگرم/متر)"),
                                 ("source_ref", "مرجع دیتایل"), ("reason", "دلیل عدم کاربرد")):
                editor = QLineEdit()
                widgets[field] = editor
                form.addRow(label, editor)
            self.bars[kind] = widgets
            column.addWidget(box)
        column.addStretch(1)
        buttons = QHBoxLayout()
        self.load_button = QPushButton("بارگذاری تیر")
        self.save_button = QPushButton("ذخیره پیش‌نویس")
        self.preview_button = QPushButton("بررسی کمیت")
        self.commit_button = QPushButton("ثبت نهایی در ریزمتره")
        for button in (self.load_button, self.save_button, self.preview_button, self.commit_button):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.message = QLabel("تا قبل از تأیید پنج قلم میلگرد، جمع وزن نهایی مسدود است.")
        self.message.setWordWrap(True)
        root.addWidget(self.message)
        self.load_button.clicked.connect(self.load)
        self.save_button.clicked.connect(self.save)
        self.preview_button.clicked.connect(self.preview)
        self.commit_button.clicked.connect(self.commit)
        self.reset_form()

    def reset_form(self):
        for kind, status in empty_beam("طبقه", "تیر")["bars"].items():
            self.bars[kind]["status"].setCurrentIndex(self.bars[kind]["status"].findData(status["status"]))
        self.revision = 0

    def _identity(self):
        project = self.project_id_getter().strip()
        floor = self.floor.text().strip()
        beam = self.beam.text().strip()
        if not project or not floor or not beam:
            raise ValueError("شناسه پروژه، طبقه و تیر باید مشخص باشند")
        return project, floor, beam

    @staticmethod
    def _maybe_number(value: str, *, integral=False):
        raw = value.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        if not raw:
            return None
        number = float(raw)
        if integral and not number.is_integer():
            raise ValueError("تعداد باید صحیح باشد")
        return int(number) if integral else number

    def _drawing_source(self):
        """Use exact drawing bytes and selected viewport rectangle, never guessed scale."""
        context = self.drawing_context_getter()
        path = Path(context.get("path", "")) if context.get("path") else None
        region = context.get("region")
        if not path or not path.is_file():
            # Manual mode remains available when the project has no drawing.
            project, floor, beam = self._identity()
            return {"mode": "manual", "source_id": f"manual:{project}:{floor}:{beam}"}
        if not region:
            return {}  # Drawing exists but has not been linked to this beam.
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        digest = sha.hexdigest()
        page = context.get("page", 1)
        fingerprint = ",".join(format(float(v), ".8g") for v in region)
        return {"mode": "drawing", "source_id": f"drawing:{digest}:page:{page}:region:{fingerprint}",
                "sha256": digest, "page": page, "drawing_path": str(path), "selected_region": list(region)}

    def _draft(self):
        project, floor, beam = self._identity()
        draft = empty_beam(floor, beam)
        source = self._drawing_source()
        # Without a verified region, preserve a draft but never claim a drawing link.
        draft["source"] = source
        reviewer = self.reviewer.text().strip()
        geometry = {"approved_by": reviewer, "source_ref": self.geometry["source_ref"].text().strip()}
        for key in ("length", "width", "depth", "count", "deductions_m3"):
            value = self._maybe_number(self.geometry[key].text(), integral=(key == "count"))
            if value is not None:
                geometry[key] = value
        draft["geometry"] = geometry
        formwork = {"approved_by": reviewer, "source_ref": self.formwork["source_ref"].text().strip()}
        area = self._maybe_number(self.formwork["net_area_m2"].text())
        if area is not None:
            formwork["net_area_m2"] = area
        draft["formwork"] = formwork
        for kind, widgets in self.bars.items():
            bar = {"status": widgets["status"].currentData()}
            if bar["status"] in ("confirmed", "not_applicable"):
                bar["approved_by"] = reviewer
                bar["source_ref"] = widgets["source_ref"].text().strip()
            if bar["status"] == "confirmed":
                for name in ("count", "cut_length_m", "unit_weight_kg_m"):
                    value = self._maybe_number(widgets[name].text(), integral=(name == "count"))
                    if value is not None:
                        bar[name] = value
            if bar["status"] == "not_applicable":
                bar["reason"] = widgets["reason"].text().strip()
            draft["bars"][kind] = bar
        return project, draft

    def load(self):
        try:
            project, floor, beam = self._identity()
            record = self.service.get_beam_detail(project, floor, beam)
            if record is None:
                draft = empty_beam(floor, beam)
                self.revision = 0
                self.message.setText("این تیر هنوز ذخیره نشده است؛ وضعیت پیش‌فرض اقلام بارگذاری شد.")
            else:
                draft = record["data"]
                self.revision = record["revision"]
                self.message.setText(f"نسخه {self.revision} بازیابی شد؛ وضعیت: {record['status']}")
            self._loaded_identity = (project, floor, beam)
            self._segmented_kinds = {
                kind for kind in BAR_TYPES if draft["bars"][kind].get("segments")
            }
            if self._segmented_kinds:
                self.message.setText("این تیر دیتایل چندبازه‌ای دارد؛ این فرم ساده تا تکمیل ویرایشگر بازه‌ها اجازه ویرایش آن را نمی‌دهد.")
            self.floor.setText(draft["floor_id"])
            self.beam.setText(draft["beam_id"])
            self.geometry["source_ref"].setText(str(draft.get("geometry", {}).get("source_ref", "")))
            for k, editor in self.geometry.items():
                if k != "source_ref":
                    editor.setText(str(draft.get("geometry", {}).get(k, "")))
            for k, editor in self.formwork.items():
                editor.setText(str(draft.get("formwork", {}).get(k, "")))
            self.reviewer.setText(str(draft.get("geometry", {}).get("approved_by", "")))
            for name in BAR_TYPES:
                data = draft["bars"][name]
                widgets = self.bars[name]
                widgets["status"].setCurrentIndex(widgets["status"].findData(data["status"]))
                for field in ("count", "cut_length_m", "unit_weight_kg_m", "source_ref", "reason"):
                    widgets[field].setText(str(data.get(field, "")))
            if record and record["status"] == "committed":
                self.save_button.setEnabled(False)
                self.commit_button.setEnabled(False)
            else:
                self.save_button.setEnabled(True)
                self.commit_button.setEnabled(True)
        except Exception as exc:
            QMessageBox.warning(self, "بارگذاری تیر", str(exc))

    def save(self):
        try:
            project, draft = self._draft()
            if self._segmented_kinds:
                raise ValueError("ویرایش دیتایل چندبازه‌ای از این فرم پشتیبانی نمی‌شود؛ داده قبلی محفوظ است")
            identity = (project, draft["floor_id"], draft["beam_id"])
            if self._loaded_identity != identity:
                existing = self.service.get_beam_detail(*identity)
                if existing:
                    raise ValueError("این تیر قبلاً ثبت شده است؛ قبل از ویرایش «بارگذاری تیر» را انتخاب کنید")
                self.revision = 0
            result = self.service.save_beam_detail_draft(project, draft, expected_revision=self.revision)
            self.revision = result["revision"]
            self._loaded_identity = identity
            self.message.setText(f"پیش‌نویس تیر در SQLite ذخیره شد؛ نسخه {self.revision}")
            return True
        except Exception as exc:
            QMessageBox.warning(self, "ذخیره متره تیر", str(exc))
            return False

    def preview(self):
        if not self.save():
            return False
        project, floor, beam = self._identity()
        result = self.service.preview_beam_detail(project, floor, beam)
        if result["ready"]:
            self.message.setText("همه اقلام تأییدشده‌اند. پیش‌نمایش: " +
                                 "؛ ".join(f"{x['description']}: {x['quantity']:.3f} {x['unit']}" for x in result["rows"]))
        else:
            self.message.setText("ثبت نهایی مسدود است: " + "؛ ".join(result["blockers"]))
        return bool(result["ready"])

    def commit(self):
        if not self.preview():
            return
        try:
            project, floor, beam = self._identity()
            report = self.service.preview_beam_detail(project, floor, beam)
            if not report["ready"]:
                return
            answer = QMessageBox.question(self, "تأیید ثبت نهایی",
                                         f"کمیت‌های تأییدشده تیر {beam} به ریزمتره منتقل شوند؟",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
            result = self.service.commit_beam_detail(project, floor, beam, expected_revision=self.revision)
            self.message.setText(f"ثبت قطعی انجام شد؛ {result['takeoff_rows']} ردیف منتقل شد.")
            self.save_button.setEnabled(False)
            self.commit_button.setEnabled(False)
        except Exception as exc:
            QMessageBox.warning(self, "ثبت نهایی", str(exc))
