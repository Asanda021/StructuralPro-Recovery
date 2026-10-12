"""Persian beam takeoff review pane for the existing graphical drawing workspace.

It does not pretend to extract rebar from CAD. Only verified measurements and
explicitly reviewed detail entries may be committed to project BOQ.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QScrollArea, QGroupBox, QInputDialog,
)

from core.takeoff.beam_detail import BAR_TYPES, BAR_LABELS, empty_beam
from core.takeoff.stirrup_zones import validate_stirrup_zones
from core.drawings.beam_detail_match import cad_beam_evidence, pdf_beam_evidence, parse_section_hint, normalize_label, BeamEvidence
from core.drawings.beam_rebar_hints import propose_rebar_from_evidence

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
        self._stirrup_segments = None
        self._selected_evidence = None
        self.setMinimumWidth(360)
        root = QVBoxLayout(self)
        title = QLabel("متره ترکیبی تیر — کنترل دیتایل")
        title.setStyleSheet("font-weight: 700")
        root.addWidget(title)
        hint = QLabel("ابتدا تیر و ناحیه آن را در نقشه انتخاب کنید. اطلاعات نامشخص را وارد و اقلام را جداگانه بررسی کنید.")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.find_labels_button = QPushButton("یافتن برچسب و مرجع دیتایل تیر در نقشه")
        root.addWidget(self.find_labels_button)
        self.suggest_rebar_button = QPushButton("پیشنهاد مشخصات میلگرد از مرجع انتخاب‌شده")
        self.suggest_rebar_button.setToolTip("فقط متن دارای شناسه تیر و نوع میلگرد را می‌خواند؛ محاسبه وزن و تأیید نهایی انجام نمی‌شود.")
        root.addWidget(self.suggest_rebar_button)
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
            for field, label in (("count", "تعداد"), ("nominal_diameter_mm", "قطر اسمی از دیتایل (میلی‌متر)"), ("cut_length_m", "طول برش تأییدشده (متر)"),
                                 ("unit_weight_kg_m", "وزن واحد (کیلوگرم/متر)"),
                                 ("source_ref", "مرجع دیتایل"), ("reason", "دلیل عدم کاربرد")):
                editor = QLineEdit()
                widgets[field] = editor
                form.addRow(label, editor)
            self.bars[kind] = widgets
            if kind == "stirrups":
                self.stirrup_zones_button = QPushButton("ویرایش نواحی چندبازه‌ای خاموت")
                self.stirrup_zones_button.setToolTip("کنترل ناحیه، فاصله، تعداد، طول برش و عدم تکرار خاموت مشترک")
                form.addRow(self.stirrup_zones_button)
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
        self.stirrup_zones_button.clicked.connect(self.edit_stirrup_zones)
        self.find_labels_button.clicked.connect(self.find_drawing_labels)
        self.suggest_rebar_button.clicked.connect(self.suggest_reinforcement)
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
        source = {"mode": "drawing", "source_id": f"drawing:{digest}:page:{page}:region:{fingerprint}",
                  "sha256": digest, "page": page, "drawing_path": str(path), "selected_region": list(region)}
        # An explicit reference selection never constitutes dimensional or rebar approval.
        linked = self._selected_evidence
        if (linked is not None and linked.get("source_id") == source["source_id"]
                and linked.get("beam_tag") == normalize_label(self.beam.text())):
            source["detail_evidence"] = dict(linked["evidence"])
        return source

    def find_drawing_labels(self):
        """Ask the engineer to select an evidence reference; never approve quantities."""
        try:
            _, _, beam_id = self._identity()
            context = self.drawing_context_getter()
            path = Path(context.get("path") or "")
            if not path.is_file():
                raise ValueError("ابتدا نقشه PDF، DWG یا DXF را باز کنید")
            region = context.get("region")
            if region is None:
                raise ValueError("ابتدا ناحیه تیر را روی نقشه انتخاب کنید")
            current_source = self._drawing_source()
            if current_source.get("mode") != "drawing":
                raise ValueError("منبع و ناحیه نقشه کامل نیست")
            page = int(context.get("page", 1))
            if context.get("cad_document") is not None:
                candidates = cad_beam_evidence(
                    context["cad_document"], beam_id, region=region,
                    scene_origin=context.get("cad_scene_origin"), page=page,
                )
            elif context.get("pdf_engine") is not None:
                # Search every page for related section/schedule tags in the same file.
                # Page text has no region coordinates; the reviewer chooses explicitly.
                reader = context["pdf_engine"]
                candidates = tuple(
                    match
                    for detail_page in range(1, reader.page_count + 1)
                    for match in pdf_beam_evidence(reader.text(detail_page), beam_id, page=detail_page)
                )
            else:
                raise ValueError("نمایشگر فعلی اطلاعات متنی قابل بررسی ندارد")
            if not candidates:
                self.message.setText(
                    "برچسب منطبق پیدا نشد؛ این به معنای نبود دیتایل نیست. بررسی دستی لازم است."
                )
                return
            ordered = sorted(candidates, key=lambda x: not x.in_selected_region)
            options = [
                ("در ناحیه انتخابی" if item.in_selected_region else "در صفحه/خارج از ناحیه")
                + f" | {item.source_ref} | {item.text[:90]}"
                for item in ordered
            ]
            choice, accepted = QInputDialog.getItem(
                self, "انتخاب مرجع دیتایل تیر",
                "مرجع پیشنهادی را با خود نقشه تطبیق دهید؛ انتخاب، کمیت را تأیید نمی‌کند:",
                options, 0, False,
            )
            if not accepted:
                return
            item = ordered[options.index(choice)]
            self._selected_evidence = {
                "source_id": current_source["source_id"], "beam_tag": normalize_label(beam_id),
                "evidence": {**item.to_dict(), "beam_tag": normalize_label(beam_id),
                             "drawing_sha256": current_source["sha256"]},
            }
            proposed = parse_section_hint(item.text, beam_id)
            if proposed is not None:
                width_text = self.geometry["width"].text().strip()
                depth_text = self.geometry["depth"].text().strip()
                if width_text or depth_text:
                    self.message.setText(
                        "مرجع دیتایل انتخاب شد؛ ابعاد موجود فرم به‌صورت خودکار بازنویسی نشدند. "
                        "برای جلوگیری از تعارض، ابعاد را دستی با نقشه تطبیق دهید."
                    )
                    return
                answer = QMessageBox.question(
                    self, "انتقال ابعاد مستند به فرم",
                    f"متن {item.source_ref} عرض {proposed['width_m']:g} متر و ارتفاع مقطع "
                    f"{proposed['depth_m']:g} متر را صریحاً ذکر می‌کند. "
                    "پس از تطبیق دستی با نقشه، این دو مقدار در فرم درج شوند؟ "
                    "این اقدام به‌معنی تأیید نهایی کمیت نیست.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self.geometry["width"].setText(format(proposed["width_m"], ".8g"))
                    self.geometry["depth"].setText(format(proposed["depth_m"], ".8g"))
                    self.geometry["source_ref"].setText(item.source_ref)
            self.message.setText(
                f"مرجع {item.source_ref} انتخاب شد. مقدارها همچنان نیازمند بازبینی هستند؛ "
                "طول، تعداد، کسر هم‌پوشانی و دیتایل پنج گروه میلگرد حدس زده نمی‌شوند."
            )
        except Exception as exc:
            QMessageBox.warning(self, "یافتن دیتایل تیر", str(exc))

    def suggest_reinforcement(self):
        """Show traceable reinforcement candidates; require explicit consent even to prefill."""
        try:
            _, _, beam_id = self._identity()
            source = self._drawing_source()
            raw = source.get("detail_evidence") if source.get("mode") == "drawing" else None
            if not isinstance(raw, dict):
                raise ValueError("ابتدا ناحیه تیر و مرجع دیتایل همین نقشه را انتخاب کنید")
            evidence = BeamEvidence(
                source_ref=str(raw["source_ref"]), text=str(raw["text"]),
                kind=str(raw["kind"]), page=int(raw["page"]),
                layer=str(raw.get("layer", "")), handle=str(raw.get("handle", "")),
                in_selected_region=bool(raw.get("in_selected_region", False)),
                located=bool(raw.get("located", False)),
            )
            result = propose_rebar_from_evidence((evidence,), beam_id)
            proposals = result["candidates"]
            if not proposals:
                self.message.setText("در متن انتخاب‌شده سری میلگرد صریح و بدون ابهام پیدا نشد؛ دیتایل را دستی بررسی کنید.")
                return
            lines = []
            for item in proposals:
                count = str(item["count"]) if item["count"] is not None else "نامشخص"
                spacing = (f" | فاصله {item['spacing_m']:g} متر" if item["spacing_m"] is not None else "")
                lines.append(f"{BAR_LABELS[item['kind']]}: {count} عدد، قطر اسمی {item['diameter_mm']:g} میلی‌متر{spacing}")
                lines.extend("  نیازمند بررسی: " + issue for issue in item["issues"])
            lines.extend(result["warnings"])
            QMessageBox.information(
                self, "پیشنهادهای آرماتور — نیازمند تأیید",
                "\n".join(lines) + "\n\nطول برش، خم، وصله، وزن واحد و تعداد خاموت حدس زده نمی‌شوند."
            )
            # Only one explicit, nonconflicting series can prefill basic fields.
            ready = [item for item in proposals if item["count"] is not None
                     and not item["issues"] and item["kind"] != "stirrups"]
            if len(proposals) != 1 or len(ready) != 1 or result["warnings"]:
                self.message.setText("چند سری یا مشخصات ناقص دیده شد؛ انتقال خودکار به فرم انجام نشد.")
                return
            proposal = ready[0]
            widgets = self.bars[proposal["kind"]]
            if (widgets["count"].text().strip() or widgets["nominal_diameter_mm"].text().strip()
                    or widgets["status"].currentData() in {"confirmed", "not_applicable"}):
                self.message.setText("مقادیر/تأیید قبلی وجود دارد؛ بازنویسی خودکار ممنوع است.")
                return
            answer = QMessageBox.question(
                self, "درج پیشنهاد در پیش‌نویس",
                f"از {proposal['source_ref']} تعداد {proposal['count']} و قطر اسمی "
                f"{proposal['diameter_mm']:g} میلی‌متر را پس از بررسی وارد فرم کنم؟ "
                "وضعیت همچنان «نیازمند تأیید» می‌ماند و محاسبه نهایی مسدود است.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            widgets["count"].setText(str(proposal["count"]))
            widgets["nominal_diameter_mm"].setText(f"{proposal['diameter_mm']:g}")
            widgets["source_ref"].setText(proposal["source_ref"])
            widgets["status"].setCurrentIndex(widgets["status"].findData("needs_review"))
            self.message.setText("پیشنهاد در فرم درج شد؛ برای محاسبه باید طول برش و وزن واحد معتبر وارد و مهندس تأیید کند.")
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "پیشنهاد آرماتور", str(exc))

    def edit_stirrup_zones(self):
        """Edit spatially validated zones; any change invalidates old approval."""
        try:
            identity = self._identity()
            if self._loaded_identity is not None and self._loaded_identity != identity:
                raise ValueError("شناسه تیر تغییر کرده؛ پیش از ویرایش نواحی، تیر جدید را بارگذاری کنید")
            length = self._maybe_number(self.geometry["length"].text())
            if length is None or length <= 0:
                raise ValueError("ابتدا طول واقعی تیر را وارد کنید")
            from app.beam_stirrup_zone_editor import StirrupZoneEditor
            dialog = StirrupZoneEditor(beam_length_m=length, zones=self._stirrup_segments, parent=self)
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            self._stirrup_segments = deepcopy(dialog.zones)
            widgets = self.bars["stirrups"]
            widgets["status"].setCurrentIndex(widgets["status"].findData("needs_review"))
            self.message.setText("نواحی خاموت در فرم بارگذاری شد؛ وضعیت به نیازمند تأیید بازگشت. ثبت قطعی هنوز مجاز نیست.")
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "ویرایش خاموت‌های چندبازه‌ای", str(exc))

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
            if bar["status"] in ("confirmed", "not_applicable", "needs_review"):
                bar["source_ref"] = widgets["source_ref"].text().strip()
            if bar["status"] in ("confirmed", "needs_review"):
                for name in ("count", "nominal_diameter_mm", "cut_length_m", "unit_weight_kg_m"):
                    value = self._maybe_number(widgets[name].text(), integral=(name == "count"))
                    if value is not None:
                        bar[name] = value
            if bar["status"] == "not_applicable":
                bar["reason"] = widgets["reason"].text().strip()
            if kind == "stirrups" and self._stirrup_segments is not None:
                if bar["status"] == "not_applicable":
                    raise ValueError("خاموت دارای ناحیه است؛ حذف کاربرد بدون اصلاح دیتایل ممنوع است")
                validate_stirrup_zones(self._stirrup_segments, geometry.get("length"))
                bar["segments"] = deepcopy(self._stirrup_segments)
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
            source = draft.get("source", {})
            evidence = source.get("detail_evidence") if isinstance(source, dict) else None
            self._selected_evidence = ({"source_id": source.get("source_id"),
                                        "beam_tag": evidence.get("beam_tag"), "evidence": dict(evidence)}
                                       if isinstance(evidence, dict) else None)
            self._stirrup_segments = deepcopy(draft["bars"]["stirrups"].get("segments"))
            self._segmented_kinds = {
                kind for kind in BAR_TYPES if kind != "stirrups" and draft["bars"][kind].get("segments")
            }
            if self._stirrup_segments:
                self.message.setText(f"{len(self._stirrup_segments)} ناحیه خاموت بارگذاری شد؛ جزئیات در ویرایشگر نواحی قابل اصلاح هستند.")
            if self._segmented_kinds:
                self.message.setText("بازه‌های غیرخاموت در فرم ساده قابل ویرایش نیستند؛ اطلاعات پیشین محفوظ است.")
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
                for field in ("count", "nominal_diameter_mm", "cut_length_m", "unit_weight_kg_m", "source_ref", "reason"):
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
                raise ValueError("ویرایش بازه‌های غیرخاموت از این فرم پشتیبانی نمی‌شود؛ داده قبلی محفوظ است")
            if self._stirrup_segments is not None and self._loaded_identity is not None:
                if self._loaded_identity != (project, draft["floor_id"], draft["beam_id"]):
                    raise ValueError("شناسه تیر تغییر کرده؛ نواحی خاموت تیر قبلی قابل انتقال نیست")
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
