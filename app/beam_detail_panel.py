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
    QComboBox, QMessageBox, QScrollArea, QGroupBox, QInputDialog, QFileDialog,
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
        self._detail_template=None;self._component_review=None
        self._advanced_geometry=False
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
        self.specialist_policy=QComboBox();self.specialist_policy.addItem('قرارداد تخصصی — کنترل دقیق و دیتایل صریح',True);self.specialist_policy.addItem('نمایش قرارداد تاریخی — نیازمند بازبینی',False)
        self.plan_ref=QLineEdit();self.detail_ref=QLineEdit();identity_form.addRow('قرارداد متره',self.specialist_policy);identity_form.addRow('مرجع پلان',self.plan_ref);identity_form.addRow('مرجع دیتایل',self.detail_ref)
        def scope():
            c=QComboBox();c.addItem('دامنه را صریح انتخاب کنید',None);c.addItem('برای هر تیر هم‌تیپ', 'per_member');c.addItem('جمع کل گروه تیرها','total_group');return c
        self.deduction_scope=scope();self.formwork_scope=scope();self.bar_scopes={};self.bar_positions={}
        self.geometry = {}
        box = QGroupBox("ابعاد و بتن تیر — واحد متر")
        f = QFormLayout(box)
        for key, label in (("length", "طول"), ("width", "عرض"),
                           ("depth", "ارتفاع مقطع"), ("count", "تعداد"),
                           ("deductions_m3", "کسر هم‌پوشانی (مترمکعب)"),
                           ("source_ref", "مرجع دیتایل ابعاد"),("cover_m","پوشش بتن (متر)"),("cover_ref","مرجع پوشش"),("deduction_scope_ref","مرجع دامنه کسورات")):
            editor = QLineEdit()
            self.geometry[key] = editor
            f.addRow(label, editor)
        f.addRow("دامنه کسورات",self.deduction_scope)
        column.addWidget(box)
        self.formwork = {}
        box = QGroupBox("قالب‌بندی — سطح خالص تأییدشده")
        f = QFormLayout(box)
        for key, label in (("net_area_m2", "مساحت خالص (مترمربع)"),
                           ("source_ref", "مرجع سطوح قالب"),("area_scope_ref","مرجع دامنه قالب")):
            editor = QLineEdit()
            self.formwork[key] = editor
            f.addRow(label, editor)
        column.addWidget(box)
        f.addRow("دامنه مساحت قالب",self.formwork_scope)
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
                                 ("unit_weight_source", "مرجع وزن واحد میلگرد"),
                                 ("source_ref", "مرجع دیتایل"), ("reason", "دلیل عدم کاربرد"),("id","شناسه مستقل میلگرد"),("cut_length_ref","مرجع طول محور برش و جزئیات خم/قلاب/مهار"),("count_scope_ref","مرجع دامنه تعداد")):
                editor = QLineEdit()
                widgets[field] = editor
                form.addRow(label, editor)
            self.bar_scopes[kind]=scope();form.addRow('دامنه تعداد',self.bar_scopes[kind])
            position=QComboBox();position.addItem('موقعیت را انتخاب کنید',None)
            for code,label in [('top','بالا'),('bottom','پایین'),('span','دهانه'),('support','تکیه‌گاه'),('side','کمرکش'),('crosstie','سنجاقی')]:position.addItem(label,code)
            self.bar_positions[kind]=position;form.addRow('موقعیت میلگرد',position)
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
        self.series_buttons={};self.detail_buttons={}
        for kind in BAR_TYPES:
            if kind=='stirrups':continue
            button=QPushButton('ویرایش چندسری '+BAR_LABELS[kind]);root.addWidget(button);self.series_buttons[kind]=button;button.clicked.connect(lambda _=False,k=kind:self.edit_components('series',k))
        for kind,label in [('sections','نواحی مقطع متغیر'),('surfaces','سطوح قالب و کسورات'),('intersections','کسورات هندسی بتن')]:
            button=QPushButton('ویرایش '+label);root.addWidget(button);self.detail_buttons[kind]=button;button.clicked.connect(lambda _=False,k=kind:self.edit_components(k))
        self.review_beam_button=QPushButton('بازبینی نسخه جاری تیر');self.edit_reason=QLineEdit();self.edit_reason.setPlaceholderText('علت ثبت یا اصلاح');root.addWidget(self.edit_reason);root.addWidget(self.review_beam_button);self.review_beam_button.clicked.connect(self.review_current)
        self.beam_amend_creator=QLineEdit();self.beam_amend_reviewer=QLineEdit();self.beam_amend_note=QLineEdit();self.beam_amend_id=QLineEdit()
        for w,label in [(self.beam_amend_creator,'سازنده اصلاحیه'),(self.beam_amend_reviewer,'بازبین مستقل اصلاحیه'),(self.beam_amend_note,'یادداشت بازبینی'),(self.beam_amend_id,'شناسه اصلاحیه')]:w.setPlaceholderText(label);root.addWidget(w)
        self.amend_create_button=QPushButton('ثبت درخواست اصلاح تیر قطعی');self.amend_review_button=QPushButton('بازبینی مستقل اصلاحیه');self.amend_apply_button=QPushButton('اعمال اتمیک اصلاحیه');self.history_button=QPushButton('تاریخچه نسخه‌های تیر')
        for b in (self.amend_create_button,self.amend_review_button,self.amend_apply_button,self.history_button):root.addWidget(b)
        self.amend_create_button.clicked.connect(lambda:self.amend('create'));self.amend_review_button.clicked.connect(lambda:self.amend('review'));self.amend_apply_button.clicked.connect(lambda:self.amend('apply'));self.history_button.clicked.connect(self.show_history)
        self.xlsx_button=QPushButton('ریزمتره تیر Excel');self.pdf_button=QPushButton('ریزمتره تیر PDF');buttons.addWidget(self.xlsx_button);buttons.addWidget(self.pdf_button)
        self.xlsx_button.clicked.connect(lambda:self.export('xlsx'));self.pdf_button.clicked.connect(lambda:self.export('pdf'))
        self.setLayoutDirection(Qt.RightToLeft)
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
        from core.commercial.exact_values import number as parse,wire
        number = parse(raw,'ورودی تیر',True)
        if integral and number!=number.to_integral_value():
            raise ValueError("تعداد باید صحیح باشد")
        return int(number) if integral else wire(number)

    def _drawing_source(self):
        """Use exact drawing bytes and selected viewport rectangle, never guessed scale."""
        context = self.drawing_context_getter() or {}
        path = Path(context.get("path", "")) if context.get("path") else None
        region = context.get("region")
        if not path or not path.is_file():
            # Manual mode remains available when the project has no drawing.
            project, floor, beam = self._identity()
            if self._detail_template and self._loaded_identity==(project,floor,beam) and self._detail_template.get("source",{}).get("mode")=="manual":return deepcopy(self._detail_template["source"])
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
            context = self.drawing_context_getter() or {}
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
            dialog = StirrupZoneEditor(beam_length_m=length, zones=self._stirrup_segments, specialist=self.specialist_policy.currentData(), parent=self)
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
        draft = deepcopy(self._detail_template) if self._detail_template and self._loaded_identity==(project,floor,beam) else empty_beam(floor, beam)
        source = self._drawing_source()
        # Without a verified region, preserve a draft but never claim a drawing link.
        if self.specialist_policy.currentData():
            draft['measurement_policy']='beam_specialist_v1'
            source.update(plan_ref=self.plan_ref.text().strip(),detail_ref=self.detail_ref.text().strip())
        draft["source"] = source
        reviewer = self.reviewer.text().strip()
        geometry = {**deepcopy(draft.get("geometry",{})),"approved_by": reviewer, "source_ref": self.geometry["source_ref"].text().strip()}
        for key in ("length", "width", "depth", "count", "deductions_m3", "cover_m"):
            value = self._maybe_number(self.geometry[key].text(), integral=(key == "count"))
            if value is not None:
                geometry[key] = value
        if self.specialist_policy.currentData():geometry.update(variable_units={'length':'m','width':'m','depth':'m','count':'عدد'},cover_ref=self.geometry['cover_ref'].text().strip())
        geometry.update(deduction_scope=self.deduction_scope.currentData(),deduction_scope_ref=self.geometry['deduction_scope_ref'].text().strip())
        if "intersections" in geometry:geometry.pop("deductions_m3",None)
        draft["geometry"] = geometry
        formwork = {**deepcopy(draft.get("formwork",{})),"approved_by": reviewer, "source_ref": self.formwork["source_ref"].text().strip()}
        area = self._maybe_number(self.formwork["net_area_m2"].text())
        if area is not None:
            formwork["net_area_m2"] = area
        formwork.update(area_scope=self.formwork_scope.currentData(),area_scope_ref=self.formwork['area_scope_ref'].text().strip())
        if "surfaces" in formwork:formwork.pop("net_area_m2",None)
        draft["formwork"] = formwork
        for kind, widgets in self.bars.items():
            bar = {**deepcopy(draft["bars"].get(kind,{})),"status": widgets["status"].currentData()}
            if bar["status"] in ("confirmed", "not_applicable"):
                bar["approved_by"] = reviewer
            if bar["status"] in ("confirmed", "not_applicable", "needs_review"):
                bar["source_ref"] = widgets["source_ref"].text().strip()
            if bar["status"] in ("confirmed", "needs_review"):
                for name in ("count", "nominal_diameter_mm", "cut_length_m", "unit_weight_kg_m"):
                    value = self._maybe_number(widgets[name].text(), integral=(name == "count"))
                    if value is not None:
                        bar[name] = value
            if bar["status"] in ("confirmed", "needs_review"):
                bar["unit_weight_source"] = widgets["unit_weight_source"].text().strip()
                bar.update(count_scope=self.bar_scopes[kind].currentData(),count_scope_ref=widgets['count_scope_ref'].text().strip())
                if self.specialist_policy.currentData():bar.update(id=widgets['id'].text().strip(),position=self.bar_positions[kind].currentData(),cut_length_ref=widgets['cut_length_ref'].text().strip())
            if bar["status"] == "not_applicable":
                bar["reason"] = widgets["reason"].text().strip()
            if kind == "stirrups" and self._stirrup_segments:
                if bar["status"] == "not_applicable":
                    raise ValueError("خاموت دارای ناحیه است؛ حذف کاربرد بدون اصلاح دیتایل ممنوع است")
                validate_stirrup_zones(self._stirrup_segments, geometry.get("length"))
                bar["segments"] = deepcopy(self._stirrup_segments)
            draft["bars"][kind] = bar
        if self._component_review:draft["component_review"]=deepcopy(self._component_review)
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
            self._detail_template=deepcopy(draft);self._component_review=None
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
                self.message.setText("سری‌های میلگرد بارگذاری شد؛ با دکمهٔ ویرایش سری‌ها، دیتایل و بازبینی هر سری را کنترل کنید.")
            self._advanced_geometry=any(k in draft.get('geometry',{}) for k in ('sections','intersections')) or 'surfaces' in draft.get('formwork',{})
            self.specialist_policy.setCurrentIndex(0 if draft.get('measurement_policy')=='beam_specialist_v1' else 1);self.plan_ref.setText(draft.get('source',{}).get('plan_ref',''));self.detail_ref.setText(draft.get('source',{}).get('detail_ref',''))
            self.deduction_scope.setCurrentIndex(max(0,self.deduction_scope.findData(draft.get('geometry',{}).get('deduction_scope'))));self.formwork_scope.setCurrentIndex(max(0,self.formwork_scope.findData(draft.get('formwork',{}).get('area_scope'))))
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
                for field in ("count", "nominal_diameter_mm", "cut_length_m", "unit_weight_kg_m",
                              "unit_weight_source", "source_ref", "reason"):
                    widgets[field].setText(str(data.get(field, "")))
                for field in ("id","cut_length_ref","count_scope_ref"):widgets[field].setText(str(data.get(field,"")))
                self.bar_scopes[name].setCurrentIndex(max(0,self.bar_scopes[name].findData(data.get('count_scope'))));self.bar_positions[name].setCurrentIndex(max(0,self.bar_positions[name].findData(data.get('position'))))
            if record and record["status"] == "committed":
                self.save_button.setEnabled(False)
                self.commit_button.setEnabled(False)
                self.stirrup_zones_button.setEnabled(False)
            else:
                self.save_button.setEnabled(True)
                self.commit_button.setEnabled(True)
                self.stirrup_zones_button.setEnabled(True)
        except Exception as exc:
            QMessageBox.warning(self, "بارگذاری تیر", str(exc))

    def save(self):
        try:
            project, draft = self._draft()
            if self._stirrup_segments is not None and self._loaded_identity is not None:
                if self._loaded_identity != (project, draft["floor_id"], draft["beam_id"]):
                    raise ValueError("شناسه تیر تغییر کرده؛ نواحی خاموت تیر قبلی قابل انتقال نیست")
            identity = (project, draft["floor_id"], draft["beam_id"])
            if self._loaded_identity != identity:
                existing = self.service.get_beam_detail(*identity)
                if existing:
                    raise ValueError("این تیر قبلاً ثبت شده است؛ قبل از ویرایش «بارگذاری تیر» را انتخاب کنید")
                self.revision = 0
            result = self.service.save_beam_detail_draft(project, draft, expected_revision=self.revision,reason=self.edit_reason.text().strip() or "ثبت پیش‌نویس")
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
                                 "؛ ".join(f"{x['description']}: {x['quantity']} "+{'m3':'متر مکعب','m2':'متر مربع','kg':'کیلوگرم'}[x['unit']] for x in result["rows"])+"؛ "+self.quantity_summary(result))
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

    def export(self,format):
        try:
            project,floor,beam=self._identity()
            path,_=QFileDialog.getSaveFileName(self,'ریزمتره مستند تیر','',format.upper()+' (*.'+format+')')
            if path:self.service.export_beam_detail_report(project,floor,beam,path,format=format);self.message.setText('گزارش از نسخه ذخیره‌شده تولید شد: '+path)
        except Exception as exc:QMessageBox.warning(self,'گزارش تیر',str(exc))

    def edit_components(self,kind,group=None):
        try:
            from app.beam_component_editor import BeamComponentEditor
            from PySide6.QtWidgets import QDialog
            project,draft=self._draft()
            if self._detail_template is None:self._detail_template=deepcopy(draft);self._loaded_identity=self._identity()
            target=self._detail_template['bars'][group] if group else self._detail_template['formwork'] if kind=='surfaces' else self._detail_template['geometry']
            key='segments' if group else kind
            dialog=BeamComponentEditor(kind,target.get(key,[]),self)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            target[key]=dialog.rows;target.pop('approved_by',None);self._component_review=None
            if group:self.bars[group]['status'].setCurrentIndex(self.bars[group]['status'].findData('needs_review'))
            self.message.setText('دیتایل تغییر کرد؛ بازبینی ردیف‌ها و نسخه جاری و ذخیره لازم است')
        except Exception as e:QMessageBox.warning(self,'دیتایل تیر',str(e))
    @staticmethod
    def quantity_summary(report):
        values=[]
        for row in report['rows']:
            params=row['params']
            if row['unit']=='m3':
                values.append('بتن ناخالص: '+str(params.get('gross_m3','نامشخص'))+'؛ بتن خالص: '+str(row['quantity'])+' متر مکعب؛ کسورات: '+str(params.get('deductions_m3','نامشخص')))
            elif row['unit']=='m2':
                values.append('قالب ناخالص: '+str(params.get('gross_area_m2') or 'ثبت نشده')+'؛ قالب خالص: '+str(row['quantity'])+' متر مربع')
        return '؛ '.join(values)

    def review_current(self):
        try:
            from core.takeoff.beam_detail import preview_beam
            from core.takeoff.manual_formula_amendments import digest
            _,draft=self._draft();draft.pop('component_review',None)
            report=preview_beam(draft,self.service.takeoff)
            if not report['ready']:raise ValueError('؛ '.join(report['blockers']))
            actor=self.reviewer.text().strip()
            if not actor:raise ValueError('بازبین لازم است')
            self._component_review={'digest':digest(draft),'reviewer':actor,'base_revision':self.revision};self.message.setText('نسخه جاری صریحاً بازبینی شد؛ ذخیره نسخه لازم است. '+self.quantity_summary(report))
        except Exception as e:QMessageBox.warning(self,'بازبینی تیر',str(e))

    def amend(self,action):
        try:
            project,floor,beam=self._identity()
            if action=='create':
                _,draft=self._draft();a=self.service.create_beam_amendment(project,floor,beam,draft,expected_revision=self.revision,created_by=self.beam_amend_creator.text(),reason=self.edit_reason.text());self.beam_amend_id.setText(a['id']);self.message.setText('درخواست مستقل ثبت شد؛ دلتا: '+str(a['delta']))
            elif action=='review':self.service.review_beam_amendment(project,self.beam_amend_id.text().strip(),expected_revision=1,reviewer=self.beam_amend_reviewer.text(),note=self.beam_amend_note.text());self.message.setText('اصلاحیه مستقل بازبینی شد؛ هنوز اعمال نشده است')
            else:self.service.apply_beam_amendment(project,self.beam_amend_id.text().strip(),expected_revision=1);self.load();self.message.setText('اصلاحیه اعمال شد؛ اصل تیر و مدارک مالی ثابت‌اند')
        except Exception as e:QMessageBox.warning(self,'اصلاحیه تیر',str(e))
    def show_history(self):
        try:
            from core.takeoff.beam_detail import _beam_key
            project,floor,beam=self._identity();key=_beam_key(floor,beam);p=self.service.open_project(project);history=[r for r in p.get('beam_detail_history',[]) if r['beam_key']==key];notes=['نسخه '+str(r['revision'])+'؛ '+r['reason'] for r in history]
            notes += ['اصلاحیه '+a['id']+'؛ '+a['reason'] for a in p.get('beam_amendments',{}).values() if a['beam_key']==key];QMessageBox.information(self,'تاریخچه تیر','\n'.join(notes) or 'سابقه اصلاح موجود نیست')
        except Exception as e:QMessageBox.warning(self,'تاریخچه',str(e))
