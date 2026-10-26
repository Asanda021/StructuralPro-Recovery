"""Persian Windows W1/A2 review-only wizard, driven by real drawing/project context."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from core.ai.contextual_takeoff import ContextualTakeoffGuide, GuidedContext, _FAMILY_TEMPLATES, _QUESTIONS, _SPECIALIST_REQUIRED



# Labels are presentation only; the canonical engine keys stay unchanged.
_INPUT_LABELS = {
    "count":"تعداد صریح","length":"طول مستند","width":"عرض مستند",
    "depth":"عمق مستند","height":"ارتفاع مستند","thickness":"ضخامت مستند",
    "openings":"بازشوهای مستند","block_length":"طول بلوک",
    "block_width":"عرض بلوک","block_height":"ارتفاع بلوک",
    "block_thickness":"ضخامت بلوک","joint_thickness":"ضخامت بند ملات",
    "cement_parts":"نسبت سیمان دارای مرجع","sand_parts":"نسبت ماسه دارای مرجع",
    "block_waste_factor":"ضریب پرت بلوک با مرجع",
    "mortar_waste_factor":"ضریب پرت ملات با مرجع",
    "topping_thickness":"ضخامت بتن رویه","joist_spacing":"فاصله تیرچه",
    "joist_width":"عرض تیرچه","joist_depth":"عمق تیرچه",
    "joist_count":"تعداد تیرچه","foam_length":"طول یونولیت",
    "foam_width":"عرض یونولیت","foam_height":"ارتفاع یونولیت",
    "foam_count":"تعداد یونولیت","block_count":"تعداد بلوک",
    "mesh_unit_weight":"وزن واحد شبکه میلگرد",
    "mesh_unit_weight_source":"مرجع وزن شبکه میلگرد",
    "cast_rib_count":"تعداد ریب بتنی","cast_rib_length_m":"طول ریب بتنی",
    "cast_rib_area_m2":"مساحت ریب بتنی","waste_factor":"ضریب پرت با مرجع",
    "formwork_sides":"وجوه قالب مستند","rebar_kg_per_m3":"مصرف میلگرد از دیتایل",
    "rebar_schedule":"جدول میلگرد معتبر","consumption_per_m2":"مصرف در متر مربع",
    "consumption_unit":"واحد مصرف","openings_scope":"دامنه بازشوها",
    "layers":"تعداد لایه‌ها","consumption_per_m2_per_layer":"مصرف هر لایه با مرجع",
    "material_spec_ref":"مرجع مصالح",
    "joist_direction":"جهت تیرچه","joist_length_ref":"مرجع طول تیرچه",
    "block_spec_ref":"مشخصات بلوک","topping_thickness_ref":"دیتایل بتن رویه",
    "thermal_rebar_detail_ref":"دیتایل میلگرد حرارتی",
    "openings_ref":"مدرک بازشوها","ownership_ref":"مرجع مالکیت",
    "rib_direction":"جهت ریب","rib_count":"تعداد ریب","rib_detail_ref":"دیتایل ریب",
    "solid_area_ref":"مدرک ناحیه توپر","opening_ref":"مرجع بازشو",
    "rib_direction_x":"جهت ریب اول","rib_direction_y":"جهت ریب دوم",
    "rib_grid_ref":"مدرک شبکه ریب","intersections_ref":"مدرک تقاطع ریب",
    "discipline":"رشته تأسیسات","operation_ref":"مرجع عملیات",
    "route_or_equipment_ref":"مرجع مسیر یا تجهیز",
    "measurement_unit_ref":"مرجع واحد متره",
}

class ContextualTakeoffDialog(QDialog):
    """Every button changes real state. Nothing can write BOQ from this dialog."""

    def __init__(self, service, context_provider, *, parent=None, open_real_form=None):
        super().__init__(parent)
        self.service=service
        self.context_provider=context_provider
        self.open_real_form=open_real_form
        self.guide=ContextualTakeoffGuide(service)
        self.active=None
        self._context=None
        self._input_snapshot=None
        self.setObjectName("Phase6P4ContextualWizard")
        self.setWindowTitle("دستیار گام‌به‌گام متره | W1 / A2")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(870,680)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel("راهنمای قواعد مصوب و فرم تخصصی | فقط پیشنهاد؛ بدون تولید مقدار و قیمت"))
        self.context_label=QLabel()
        self.context_label.setObjectName("P4LiveContext")
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)
        row=QHBoxLayout()
        self.family=QComboBox()
        self.family.setObjectName("P4OperationSelector")
        for code, questions in _QUESTIONS.items():
            self.family.addItem({
                "joist_block":"سقف تیرچه بلوک","joist_foam":"سقف تیرچه یونولیت",
                "solid_slab":"دال بتنی","block_wall":"دیوار بلوکی",
                "wall_with_opening":"دیوار با بازشو",
                "waffle_one_way":"وافل یک‌طرفه","waffle_two_way":"وافل دوطرفه",
                "mep":"تأسیسات برق/مکانیک","floor_finish":"کف‌سازی",
                "false_ceiling":"سقف کاذب","beam":"تیر بتنی",
                "column":"ستون بتنی"}.get(code,code),code)
        row.addWidget(self.family)
        self.refresh_button=QPushButton("خواندن دوباره زمینه")
        self.refresh_button.setObjectName("P4RefreshContext")
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        area=QWidget()
        area_layout=QVBoxLayout(area)
        self.questions_layout=QVBoxLayout()
        area_layout.addLayout(self.questions_layout)
        self.inputs_layout=QFormLayout()
        area_layout.addLayout(self.inputs_layout)
        scroll.setWidget(area)
        layout.addWidget(scroll,1)
        self.question_checks=[]
        self.inputs={}
        self.status=QLabel("عملیات و طبقه واقعی را بررسی کنید.")
        self.status.setObjectName("P4ReviewStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        question_row=QHBoxLayout()
        self.question_input=QLineEdit()
        self.question_input.setObjectName("P4ContextQuestion")
        self.question_input.setPlaceholderText("پرسش فارسی درباره عضو، متره یا BOQ فعلی")
        self.ask_button=QPushButton("پاسخ مستند آفلاین")
        self.ask_button.setObjectName("P4AskContext")
        self.ask_button.clicked.connect(self.ask)
        question_row.addWidget(self.question_input)
        question_row.addWidget(self.ask_button)
        layout.addLayout(question_row)
        controls=QHBoxLayout()
        self.preview_button=QPushButton("نمایش پیشنهاد مستند")
        self.preview_button.setObjectName("P4Preview")
        self.review_button=QPushButton("ثبت تصمیم بازبینی (بدون BOQ)")
        self.review_button.setObjectName("P4ReviewOnly")
        self.review_button.setEnabled(False)
        self.open_form_button=QPushButton("بازکردن فرم متره واقعی")
        self.open_form_button.setObjectName("P4OpenRealForm")
        self.open_form_button.setEnabled(False)
        self.disable_button=QPushButton("خاموش‌کردن دستیار")
        self.disable_button.setObjectName("P4DisableAssistant")
        self.cancel_button=QPushButton("لغو پیشنهاد")
        self.cancel_button.setObjectName("P4Cancel")
        for button in (self.preview_button,self.review_button,self.open_form_button,self.disable_button,self.cancel_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.family.currentIndexChanged.connect(self._rebuild_form)
        self.refresh_button.clicked.connect(self.refresh_context)
        self.preview_button.clicked.connect(self.preview)
        self.review_button.clicked.connect(self.review)
        self.open_form_button.clicked.connect(self.open_form)
        self.disable_button.clicked.connect(self.toggle_enabled)
        self.cancel_button.clicked.connect(self.cancel)
        self._rebuild_form()
        self.refresh_context()

    def _clear_layout(self, layout):
        while layout.count():
            item=layout.takeAt(0)
            child=item.widget()
            if child is not None:
                child.deleteLater()

    def _rebuild_form(self,*_):
        self.cancel()
        self._clear_layout(self.questions_layout)
        self._clear_layout(self.inputs_layout)
        self.question_checks=[]
        self.inputs={}
        family=self.family.currentData()
        for question in _QUESTIONS[family]:
            check=QCheckBox(question)
            check.setTristate(True)
            check.setCheckState(Qt.CheckState.PartiallyChecked)
            check.setToolTip("نامشخص = نیازمند مدرک؛ تیک کامل = نگه‌داری برای بررسی؛ بدون تیک = رد")
            self.questions_layout.addWidget(check)
            self.question_checks.append(check)
        templates=_FAMILY_TEMPLATES[family]
        keys=list(_SPECIALIST_REQUIRED.get(family, ()))
        for code in templates:
            item=self.guide.templates.get(code)
            keys.extend(item.required_inputs)
            keys.extend(item.optional_inputs)
        for name in dict.fromkeys(keys):
            field=QLineEdit()
            field.setObjectName("P4Input_"+name)
            field.setPlaceholderText("ورودی صریح از مدرک معتبر؛ خالی یعنی نامشخص")
            self.inputs_layout.addRow(_INPUT_LABELS.get(name,name),field)
            field.textChanged.connect(self._invalidate_on_edit)
            self.inputs[name]=field

    def _invalidate_on_edit(self, *_):
        if self.active is not None:
            self.cancel()
            self.status.setText("ورودی تغییر کرد؛ پیش‌نمایش تازه لازم است.")

    def refresh_context(self):
        self.cancel()
        try:
            context=self.context_provider(self.family.currentData())
            # A proposal must never linger across a source/project switch.
            self.cancel()
            self._context=context
            self.context_label.setText(
                f"پروژه: {context.project_id} | طبقه: {context.floor_id} | "
                f"عضو: {context.member_id or 'انتخاب نشده'} | "
                f"منبع: {context.source_id or 'متره دستی'} | "
                f"Revision: {context.revision or 'فاقد'} | "
                f"هویت: {context.review_status}")
        except Exception as exc:
            self._context=None
            self.context_label.setText("زمینه واقعی در دسترس نیست.")
            self.status.setText("خطای زمینه: "+str(exc))

    def preview(self):
        self.refresh_context()
        if self._context is None:
            return None
        try:
            inputs={k:f.text().strip() for k,f in self.inputs.items() if f.text().strip()}
            proposal=self.guide.propose(self._context,inputs=inputs)
            self.active=proposal
            self._input_snapshot=inputs.copy()
            self.review_button.setEnabled(True)
            self.open_form_button.setEnabled(True)
            notes=("ورودی‌های ناقص: "+", ".join(proposal.missing_inputs)
                   if proposal.missing_inputs else "ورودی‌های قالب موجودند؛ محاسبه رسمی انجام نشده.")
            self.status.setText(notes+"\n"+"\n".join(proposal.limitations)+
                                "\nپیشنهاد هنوز تأیید مهندسی و قابلیت ثبت BOQ ندارد.")
            return proposal
        except Exception as exc:
            self.cancel()
            self.status.setText("پیشنهاد صادر نشد: "+str(exc))
            return None

    def _assert_live(self):
        if self._context is None:
            raise ValueError("زمینه فعال وجود ندارد.")
        live=self.context_provider(self.family.currentData())
        if live!=self._context:
            raise RuntimeError("پروژه، عضو یا منبع فعال تغییر کرده است؛ پیشنهاد قبلی معتبر نیست.")
        if self._input_snapshot!={k:f.text().strip() for k,f in self.inputs.items()
                                  if f.text().strip()}:
            raise RuntimeError("ورودی‌های فرم تغییر کرده‌اند؛ پیش‌نمایش را دوباره اجرا کنید.")
        self.guide.check_current(self.active)

    def review(self):
        if self.active is None:
            return None
        try:
            self._assert_live()
            accepted=tuple(x.text() for x in self.question_checks
                           if x.checkState()==Qt.CheckState.Checked)
            rejected=tuple(x.text() for x in self.question_checks
                           if x.checkState()==Qt.CheckState.Unchecked)
            pending=tuple(x.text() for x in self.question_checks
                          if x.checkState()==Qt.CheckState.PartiallyChecked)
            result=self.guide.review(self.active,accepted=accepted,rejected=rejected)
            self.status.setText(f"{len(accepted)} قلم برای بررسی نگه داشته شد؛ "
                                f"{len(rejected)} قلم رد شد؛ "
                                f"{len(pending)} قلم هنوز نیازمند مدرک است. "
                                "ثبت قطعی و تأیید مهندسی انجام نشد.")
            return result
        except Exception as exc:
            self.cancel()
            self.status.setText("بازبینی رد شد: "+str(exc))
            return None

    def open_form(self):
        if self.active is None or self.open_real_form is None:
            self.status.setText("فرم عملیاتی معتبر برای این انتخاب وصل نشده است.")
            return None
        try:
            self._assert_live()
            result=self.open_real_form(self._context)
            if result is None:
                raise ValueError("فرم عملیاتی برای این خانواده هنوز در دسترس نیست.")
            self.status.setText("فرم اصلی باز شد؛ ثبت مقدار فقط با کنترل و تأیید مستقل همان فرم.")
            return result
        except Exception as exc:
            self.cancel()
            self.status.setText("انتقال به فرم اصلی انجام نشد: "+str(exc))
            return None

    def ask(self):
        if not self.guide.enabled:
            self.status.setText("دستیار خاموش است.")
            return None
        try:
            live=self.context_provider(self.family.currentData())
            if self.active is not None and self._context!=live:
                raise RuntimeError("زمینه درخواست تغییر کرده؛ پیشنهاد قبلی لغو شود.")
            result=self.guide.answer_contextual_question(live,self.question_input.text())
            self.status.setText(result["answer"])
            return result
        except Exception as exc:
            self.cancel()
            self.status.setText("پاسخ صادر نشد: "+str(exc))
            return None

    def toggle_enabled(self):
        if self.guide.enabled:
            self.guide.disable()
            self.cancel()
            self.disable_button.setText("روشن‌کردن دستیار")
            self.preview_button.setEnabled(False)
            self.status.setText("دستیار خاموش است؛ متره دستی اصلی همچنان فعال است.")
        else:
            self.guide.enable()
            self.disable_button.setText("خاموش‌کردن دستیار")
            self.preview_button.setEnabled(True)
            self.status.setText("راهنمای آفلاین قواعد مصوب فعال شد؛ مدل خارجی اجرا نمی‌شود.")

    def cancel(self):
        if self.active is not None:
            self.guide.cancel(self.active.id)
        self.active=None
        self._input_snapshot=None
        self.review_button.setEnabled(False)
        self.open_form_button.setEnabled(False)
        self.status.setText("پیشنهاد لغو شد؛ BOQ و نشست نقشه تغییر نکرده‌اند.")
