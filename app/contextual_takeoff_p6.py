"""Phase 6 P4: real RTL step-by-step assembly and offline contextual assistant."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget, QTextEdit,
)

from core.ai.contextual_takeoff_p6 import (
    GovernedTakeoffAssistant, SPECIALIST_ONLY,
)


# Display labels only. Internal parameter keys remain the approved engine keys.
INPUT_LABELS = {
    "count":"تعداد واقعی","length":"طول (متر)","width":"عرض (متر)",
    "height":"ارتفاع (متر)","depth":"عمق (متر)","thickness":"ضخامت (متر)",
    "openings":"مساحت بازشو/کسور (مترمربع)","deductions":"طول کسور (متر)",
    "topping_thickness":"ضخامت بتن رویه","joist_spacing":"فاصله واقعی تیرچه‌ها",
    "joist_width":"عرض تیرچه","joist_depth":"عمق تیرچه",
    "joist_count":"تعداد تیرچه طبق چیدمان واقعی",
    "foam_length":"طول یونولیت","foam_width":"عرض یونولیت",
    "foam_height":"ارتفاع یونولیت","foam_count":"تعداد واقعی یونولیت",
    "block_length":"طول بلوک","block_width":"عرض بلوک",
    "block_height":"ارتفاع بلوک","block_count":"تعداد واقعی بلوک",
    "block_thickness":"ضخامت بلوک","joint_thickness":"ضخامت بند ملات",
    "cement_parts":"نسبت سیمان ملات","sand_parts":"نسبت ماسه ملات",
    "mesh_unit_weight":"وزن واحد مش مستند",
    "mesh_unit_weight_source":"مرجع دیتایل مش",
    "cast_rib_count":"تعداد جان بتنی درجا",
    "cast_rib_length_m":"طول واقعی جان بتنی درجا",
    "cast_rib_area_m2":"سطح مقطع مستند جان",
    "formwork_sides":"تعداد وجوه قالب",
    "rebar_schedule":"برنامه میلگرد با جزئیات مستقل",
    "unit_weight":"وزن واحد واقعی","waste_factor":"ضریب پرت مستند",
    "block_waste_factor":"پرت بلوک","mortar_waste_factor":"پرت ملات",
    "consumption_per_m2":"مصرف در مترمربع",
    "consumption_per_m2_per_layer":"مصرف در هر لایه/مترمربع",
    "consumption_per_m":"مصرف در مترطول",
    "consumption_unit":"واحد مصرف","material_spec_ref":"شماره مرجع مصالح",
    "layers":"تعداد لایه/دست","openings_scope":"دامنه کسور",
}

class ContextualTakeoffDialog(QDialog):
    """Model-free local assistance by default, with explicit source/approval gates."""

    def __init__(self, service, project_id, parent=None, *, floor_id="", member_id="",
                 document_path="", document_sha256="", revision="", global_id="",
                 context_guard=None):
        super().__init__(parent)
        self.setObjectName("P6W1A2TakeoffWizard")
        self.setWindowTitle("دستیار مرحله‌ای متره — W1 / A2 | فقط با منبع معتبر")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1080,800)
        self.service = service
        self.pid = project_id
        self.context_guard = context_guard
        self.document_context = dict(document_path=document_path,
                                     document_sha256=document_sha256,
                                     revision=revision,global_id=global_id)
        self.assistant = None
        self.last_preview = None
        self.fields = {}
        root=QVBoxLayout(self)
        root.addWidget(QLabel(
            "۱. پروژه و عضو واقعی  ← ۲. انتخاب عملیات  ← ۳. ورود دیتایل  ← "
            "۴. پیشنهاد و کنترل  ← ۵. ثبت فقط با تأیید و CAS"))
        self.info=QLabel("داده پروژه فقط خواندنی است؛ مقدار و قیمت فرضی مجاز نیست.")
        self.info.setWordWrap(True)
        root.addWidget(self.info)
        p=service.open_project(project_id)
        if not isinstance(p,dict):
            raise KeyError("پروژه پیدا نشد.")
        form=QFormLayout()
        self.project_label=QLabel(f"{p.get('name','')} | {project_id}")
        form.addRow("پروژه:",self.project_label)
        self.floor=QComboBox();self.floor.setObjectName("P6W1Floor")
        self.floor.addItem("انتخاب طبقه واقعی", "")
        for x in p.get("floors",[]) or []:
            self.floor.addItem(str(x.get("name") or x.get("id")),x.get("id"))
        self.member=QComboBox();self.member.setObjectName("P6W1Member")
        self.member.addItem("انتخاب عضو واقعی", "")
        form.addRow("طبقه:",self.floor)
        form.addRow("عضو:",self.member)
        self.code=QComboBox();self.code.setObjectName("P6W1Assembly")
        from core.takeoff.assembly_templates import AssemblyTemplateLibrary
        self.library=AssemblyTemplateLibrary()
        self.code.addItem("انتخاب خانواده متره", "")
        for x in self.library.list():
            self.code.addItem(x.title_fa,x.code)
        for code,title in SPECIALIST_ONLY.items():
            self.code.addItem(title + " — انتقال به فرم تخصصی",code)
        form.addRow("نوع عملیات:",self.code)
        self.measurement=QLineEdit()
        self.measurement.setObjectName("P6W1SourceReference")
        self.measurement.setPlaceholderText("شناسه صریح برداشت/دیتایل/محل؛ خودکار ساخته نمی‌شود")
        form.addRow("مرجع برداشت:",self.measurement)
        root.addLayout(form)
        self.fields_scroll=QScrollArea()
        self.fields_scroll.setWidgetResizable(True)
        self.fields_container=QWidget()
        self.fields_form=QFormLayout(self.fields_container)
        self.fields_scroll.setWidget(self.fields_container)
        root.addWidget(self.fields_scroll,2)
        tools=QHBoxLayout()
        self.preview_button=QPushButton("بررسی ورودی‌ها و پیش‌نمایش")
        self.preview_button.setObjectName("P6W1Preview")
        self.preview_button.clicked.connect(self.preview)
        self.open_manual_button=QPushButton("بازکردن فرم متره دستی موجود")
        self.open_manual_button.setObjectName("P6W1OpenManual")
        self.open_manual_button.clicked.connect(self.open_manual)
        self.specialist_button=QPushButton("بازکردن دیتایل تخصصی سقف موجود")
        self.specialist_button.setObjectName("P6W1OpenRoofSpecialist")
        self.specialist_button.clicked.connect(self.open_specialist)
        self.specialist_button.setEnabled(False)
        tools.addWidget(self.specialist_button)
        self.cancel_button=QPushButton("لغو / پاک‌کردن پیش‌نمایش")
        self.cancel_button.setObjectName("P6W1Cancel")
        self.cancel_button.clicked.connect(self.cancel_preview)
        for b in (self.preview_button,self.open_manual_button,self.cancel_button):
            tools.addWidget(b)
        root.addLayout(tools)
        self.preview_text=QTextEdit()
        self.preview_text.setObjectName("P6W1ReadOnlyPreview")
        self.preview_text.setReadOnly(True)
        root.addWidget(self.preview_text,2)
        qrow=QHBoxLayout()
        self.offline_enabled=QCheckBox("پیشنهادهای A2 آفلاین (بدون اتصال شبکه)")
        self.offline_enabled.setObjectName("P6A2Enable")
        self.offline_enabled.setChecked(True)
        self.query=QLineEdit()
        self.query.setObjectName("P6A2Question")
        self.query.setPlaceholderText("مثلاً: برای سقف تیرچه بلوک چه مواردی کم است؟")
        self.answer_button=QPushButton("پاسخ زمینه‌محور")
        self.answer_button.setObjectName("P6A2Answer")
        self.answer_button.clicked.connect(self.answer)
        qrow.addWidget(self.offline_enabled)
        qrow.addWidget(self.query,1)
        qrow.addWidget(self.answer_button)
        root.addLayout(qrow)
        boqrow=QHBoxLayout()
        self.boq_select=QComboBox()
        self.boq_select.setObjectName("P6A2VerifiedBOQRow")
        self.boq_refresh=QPushButton("بازخوانی BOQ ثبت‌شده")
        self.boq_refresh.setObjectName("P6A2RefreshBOQ")
        self.boq_refresh.clicked.connect(self.refresh_boq)
        self._boq_digest=""
        boqrow.addWidget(QLabel("ردیف برای پاسخ عددی مستند:"))
        boqrow.addWidget(self.boq_select,1)
        boqrow.addWidget(self.boq_refresh)
        root.addLayout(boqrow)
        self.refresh_boq()
        self.answer_text=QLabel("پاسخ فقط از داده واقعی و قواعد موجود؛ مدل محلی الزامی نیست.")
        self.answer_text.setWordWrap(True)
        self.answer_text.setObjectName("P6A2AnswerText")
        root.addWidget(self.answer_text)
        commit=QHBoxLayout()
        self.approver=QComboBox()
        self.approver.setObjectName("P6W1Approver")
        self.approver.addItem("انتخاب تأییدکننده مجاز", "")
        collab=getattr(service,"collaboration",None)
        if collab is not None:
            for uid,user in sorted(collab.users.items()):
                if collab.roles[user.role].allows("approve"):
                    self.approver.addItem(uid,uid)
        self.commit_button=QPushButton("ثبت اسمبلی تأییدشده در پروژه")
        self.commit_button.setObjectName("P6W1Commit")
        self.commit_button.setEnabled(False)
        self.commit_button.clicked.connect(self.commit)
        commit.addWidget(QLabel("تأییدکننده:"))
        commit.addWidget(self.approver)
        commit.addWidget(self.commit_button)
        root.addLayout(commit)
        self.floor.currentIndexChanged.connect(self.populate_members)
        self.member.currentIndexChanged.connect(self.invalidate)
        self.code.currentIndexChanged.connect(self.populate_fields)
        self.measurement.textChanged.connect(self.invalidate)
        self.approver.currentIndexChanged.connect(self.invalidate)
        if floor_id:
            index=self.floor.findData(floor_id)
            if index>=0:self.floor.setCurrentIndex(index)
        if member_id:
            index=self.member.findData(member_id)
            if index>=0:self.member.setCurrentIndex(index)

    def _guard(self):
        if self.context_guard is not None:
            self.context_guard()

    def populate_members(self,*_):
        self.invalidate()
        floor=self.floor.currentData()
        self.member.clear()
        self.member.addItem("انتخاب عضو واقعی","")
        project=self.service.open_project(self.pid)
        for m in project.get("members",[]) or []:
            if m.get("floor_id")==floor:
                self.member.addItem(str(m.get("id")),m.get("id"))

    def populate_fields(self,*_):
        self.invalidate()
        while self.fields_form.count():
            item=self.fields_form.takeAt(0)
            widget=item.widget()
            if widget is not None:widget.deleteLater()
        self.fields={}
        code=self.code.currentData()
        if code in ("waffle_one_way","waffle_two_way","hollowcore"):
            self.specialist_button.setEnabled(True)
        else:
            self.specialist_button.setEnabled(False)
        if not code or code in SPECIALIST_ONLY:
            return
        template=self.library.get(code)
        for name in template.required_inputs+template.optional_inputs:
            widget=QLineEdit()
            widget.setObjectName("P6W1Field_"+name)
            widget.setPlaceholderText("صریح وارد کنید؛ خالی یعنی نامشخص")
            widget.textChanged.connect(self.invalidate)
            self.fields[name]=widget
            label=INPUT_LABELS.get(name,name)+(" *" if name in template.required_inputs else " (اختیاری)")
            self.fields_form.addRow(label,widget)

    def inputs(self):
        import json
        result={}
        for name,widget in self.fields.items():
            value=widget.text().strip()
            if not value:
                continue
            if name=="rebar_schedule":
                try:
                    value=json.loads(value)
                except (ValueError,TypeError) as exc:
                    raise ValueError("برنامه میلگرد باید JSON معتبر با مرجع صریح باشد.") from exc
                if not isinstance(value,list):
                    raise ValueError("برنامه میلگرد باید فهرست JSON باشد.")
            result[name]=value
        return result

    def invalidate(self,*_):
        self.last_preview=None
        if hasattr(self,"commit_button"):
            self.commit_button.setEnabled(False)

    def _make_assistant(self):
        self._guard()
        return GovernedTakeoffAssistant(
            self.service,self.pid,floor_id=self.floor.currentData() or "",
            member_id=self.member.currentData() or "",**self.document_context)

    def preview(self):
        self.invalidate()
        try:
            self.assistant=self._make_assistant()
            result=self.assistant.preview(self.code.currentData() or "",
                self.inputs(),measurement_source=self.measurement.text().strip())
            parts=[
                "خانواده: "+result.title,
                "پروژه/منبع: "+self.pid+" | CAS: "+result.project_digest,
                "ورودی‌های الزامی ناقص: "+("، ".join(result.missing) or "ندارد"),
                "موانع: "+("؛ ".join(result.blockers) or "ندارد"),
                "اقلام برای بررسی مستقل: "+("، ".join(x["title"] for x in result.companions) or "ندارد"),
                "چک‌لیست تأیید مستقل (بدون مقدار فرضی):",
                *result.review_questions,
                "اجزای محاسبه‌شده فقط پیش‌نمایش فنی (غیرمالی):",
            ]
            parts += [c["title"]+" | "+c["quantity"]+" "+c["unit"]+
                      " | "+c["formula"]+" | "+c["warning"] for c in result.components]
            parts.append("این پیش‌نمایش به‌معنای تأیید محاسبات/مالی نیست.")
            self.preview_text.setPlainText("\n".join(parts))
            self.last_preview=result
            self.commit_button.setEnabled(result.ready_to_review and bool(self.approver.currentData()))
            return result
        except (ValueError,KeyError,RuntimeError,PermissionError) as error:
            self.preview_text.setPlainText("بازبینی رد شد: "+str(error))
            return None

    def refresh_boq(self):
        self.boq_select.clear()
        self.boq_select.addItem("بدون ردیف — اعداد حدسی ممنوع",None)
        try:
            self._guard()
            project=self.service.open_project(self.pid)
            self._boq_digest=self.service.store.current_digest(self.pid)
            for index,row in enumerate(project.get("boq",[]) or []):
                if not isinstance(row,dict) or row.get("status","active")!="active":
                    continue
                if not row.get("source_ids") or row.get("quantity") is None:
                    continue
                self.boq_select.addItem(
                    f"ردیف {index+1} | {row.get('description','بدون شرح')}",index)
        except (RuntimeError,ValueError,KeyError,PermissionError) as exc:
            self._boq_digest=""
            self.answer_text.setText("بازخوانی BOQ رد شد: "+str(exc)) if hasattr(self,"answer_text") else None

    def answer(self):
        if not self.offline_enabled.isChecked():
            self.answer_text.setText("A2 غیرفعال است؛ هیچ پرسش یا داده‌ای ارسال نشده است.")
            return None
        try:
            self.assistant=self._make_assistant()
            result=self.assistant.advise(
                self.query.text() or "چه ورودی‌هایی لازم است؟",
                code=self.code.currentData() or "",inputs=self.inputs(),
                measurement_source=self.measurement.text(),
                boq_row_index=self.boq_select.currentData(),
                boq_digest=self._boq_digest)
            self.answer_text.setText(result["text"])
            return result
        except (ValueError,KeyError,RuntimeError,PermissionError) as error:
            self.answer_text.setText("دستیار از ادامه خودداری کرد: "+str(error))
            return None

    def cancel_preview(self):
        if self.assistant is not None:self.assistant.cancel()
        self.invalidate()
        self.preview_text.clear()
        self.answer_text.setText("پیشنهادهای قبلی لغو شدند؛ برای کار جدید دوباره بازبینی کنید.")

    def open_specialist(self):
        self._guard()
        code=self.code.currentData()
        kind={"hollowcore":"hollow_core_detail",
              "waffle_one_way":"waffle_one_way",
              "waffle_two_way":"waffle_two_way"}.get(code)
        if kind is None:
            self.preview_text.setPlainText(
                "این مسیر نیازمند فرم تخصصی است؛ تولید عدد یا مدل ساختگی ممنوع.")
            return None
        if not self.floor.currentData():
            self.preview_text.setPlainText("اول طبقه واقعی را انتخاب کنید.")
            return None
        from app.roof_detail_editor import open_roof_editor
        return open_roof_editor(self.service,parent=self,
            project_id=self.pid,floor_id=self.floor.currentData(),kind=kind)

    def open_manual(self):
        self._guard()
        from app.manual_takeoff import ManualTakeoffDialog
        dialog=ManualTakeoffDialog(self.service,self.pid,self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if self.floor.currentData():
            dialog.floor_id.setText(self.floor.currentData())
        self._manual_dialog=dialog
        dialog.show()
        return dialog

    def commit(self):
        try:
            self._guard()
            if self.last_preview is None or not self.last_preview.ready_to_review:
                raise ValueError("ابتدا پیش‌نمایش معتبر و بدون مانع لازم است.")
            if not self.approver.currentData():
                raise PermissionError("تأییدکننده با مجوز لازم انتخاب نشده است.")
            if QMessageBox.question(
                self,"تأیید صریح ثبت اسمبلی",
                "فقط اجزای همین پیش‌نمایش با CAS فعلی در پروژه ذخیره شوند؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return None
            result=self.assistant.commit(
                code=self.code.currentData(),inputs=self.inputs(),
                measurement_source=self.measurement.text().strip(),
                approver=self.approver.currentData(),
                expected_digest=self.last_preview.project_digest)
            self.invalidate()
            self.preview_text.append("ثبت واقعی با CAS انجام شد؛ دفتر BOQ پروژه دوباره خوانده شود.")
            return result
        except (ValueError,KeyError,RuntimeError,PermissionError) as error:
            self.invalidate()
            self.preview_text.append("ثبت رد شد: "+str(error))
            return None
