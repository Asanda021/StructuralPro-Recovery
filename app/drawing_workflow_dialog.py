"""Persian, non-blocking drawing intake and editable schedule workbench.

Keeps the CAD canvas available. All detected structural types and initial
durations are preliminary proposals requiring explicit human review.
"""
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QGraphicsScene, QGraphicsView,
    QLineEdit, QInputDialog, QFileDialog, QCalendarWidget, QSpinBox, QDoubleSpinBox,
)

from core.drawings.workflow_planning import edit_activity


_KIND_LABELS = (
    ("unknown", "نامشخص؛ تعیین توسط مهندس"),
    ("concrete", "اسکلت بتنی"),
    ("steel", "اسکلت فولادی"),
    ("mixed", "اسکلت مختلط بتنی و فولادی"),
)
_DISCIPLINE_LABELS = (
    ("architecture", "معماری، نما و نازک‌کاری"),
    ("mechanical", "تأسیسات مکانیکی"),
    ("electrical", "تأسیسات الکتریکی"),
    ("elevator", "آسانسور"),
    ("fire", "اعلام و اطفای حریق"),
    ("site", "محوطه‌سازی"),
    ("wood", "سازه و نازک‌کاری چوبی"),
    ("renovation", "بازسازی و مقاوم‌سازی"),
    ("restoration", "مرمت و احیای ساختمان"),
)


class DrawingWorkflowIntakeDialog(QDialog):
    def __init__(self, source_name: str, evidence: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("پس از بازکردن نقشه | چه کاری انجام دهیم؟")
        self.setObjectName("DrawingWorkflowIntakeDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(680, 690)
        main = QVBoxLayout(self)
        intro = QLabel("از این نقشه چه می‌خواهید؟ ابتدا نوع اسکلت را بررسی کن و رشته‌های متره را انتخاب کن.")
        intro.setWordWrap(True)
        main.addWidget(intro)
        main.addWidget(QLabel("فایل: " + source_name))
        main.addWidget(QLabel("۱. مبنای صورت‌وضعیت این نقشه را انتخاب کن:"))
        self.pricing_mode=QComboBox()
        self.pricing_mode.setObjectName("DrawingInitialStatementBasis")
        self.pricing_mode.addItem("انتخاب مبنا الزامی است",None)
        self.pricing_mode.addItem("با فهرست‌بها","pricebook")
        self.pricing_mode.addItem("بدون فهرست‌بها / نرخ توافقی","contract_rates")
        main.addWidget(self.pricing_mode)
        self.contract_price_entry=QComboBox()
        self.contract_price_entry.setObjectName("DrawingContractPriceEntry")
        self.contract_price_entry.addItem("مبالغ قرارداد از ابتدا نمایش داده شود","prefilled")
        self.contract_price_entry.addItem("مبلغ خالی بماند تا اپراتور هنگام بررسی وارد کند","operator_blank")
        self.contract_price_entry.setEnabled(False)
        self.pricing_mode.currentIndexChanged.connect(
            lambda:self.contract_price_entry.setEnabled(
                self.pricing_mode.currentData()=="contract_rates"
            )
        )
        main.addWidget(self.contract_price_entry)
        main.addWidget(QLabel("۲. آیا نرم‌افزار برنامه زمان‌بندی خودکار ایجاد کند؟"))
        self.automatic_schedule=QComboBox()
        self.automatic_schedule.setObjectName("DrawingAutomaticSchedulingChoice")
        self.automatic_schedule.addItem("انتخاب کنید",None)
        self.automatic_schedule.addItem("بله، همراه متره زمان‌بندی پیشنهادی بساز","yes")
        self.automatic_schedule.addItem("خیر، فقط متره؛ برنامه هفتگی خودکار ساخته نمی‌شود","no")
        main.addWidget(self.automatic_schedule)
        main.addWidget(QLabel("۳. چند سرپرست برای رشته‌های سازه، معماری، مکانیک و برق دارید؟"))
        self.supervision_count=QComboBox()
        self.supervision_count.setObjectName("DrawingSupervisorCount")
        self.supervision_count.addItem("یک سرپرست کل رشته‌ها",1)
        self.supervision_count.addItem("دو سرپرست با تقسیم رشته‌ها",2)
        self.supervision_count.addItem("سه سرپرست با تقسیم رشته‌ها",3)
        self.supervision_count.addItem("چهار سرپرست تخصصی",4)
        main.addWidget(self.supervision_count)
        self.supervision_edit=QPushButton("تعیین نام سرپرستان و رشته مسئولیت")
        self.supervision_edit.setObjectName("ConfigureSupervisorResponsibilities")
        main.addWidget(self.supervision_edit)
        self.supervision_summary=QLabel("")
        self.supervision_summary.setWordWrap(True)
        main.addWidget(self.supervision_summary)
        self.start_date_button=QPushButton("انتخاب تاریخ شروع پروژه از تقویم")
        self.start_date_button.setObjectName("ChooseProjectStartDateFromCalendar")
        self.start_date_button.clicked.connect(self._choose_project_date)
        self.start_date_label=QLabel("تاریخ شروع پروژه انتخاب نشده است")
        self.start_date_label.setObjectName("SelectedProjectStartDate")
        self._selected_start_date=None
        main.addWidget(self.start_date_button)
        main.addWidget(self.start_date_label)
        main.addWidget(QLabel("۴. تعداد طبقات و سطح متره برای برآورد زمان:"))
        self.building_floors=QSpinBox()
        self.building_floors.setObjectName("BuildingFloorCount")
        self.building_floors.setRange(1,200)
        self.building_floors.setValue(1)
        main.addWidget(self.building_floors)
        self.typical_floor_area=QDoubleSpinBox()
        self.typical_floor_area.setObjectName("BuildingTypicalFloorArea")
        self.typical_floor_area.setRange(0,1000000)
        self.typical_floor_area.setSuffix(" متر مربع سطح هر طبقه")
        self.typical_floor_area.setDecimals(2)
        self.typical_floor_area.setValue(0)
        main.addWidget(self.typical_floor_area)
        self.only_typical_floor=QCheckBox(
            "نقشه و متره فقط یک طبقه تیپ است؛ برای طبقات همسان تکرار شود"
        )
        self.only_typical_floor.setObjectName("ConfirmSingleTypicalFloorSource")
        main.addWidget(self.only_typical_floor)
        self.repeat_floors=QSpinBox()
        self.repeat_floors.setObjectName("RepeatedTypicalFloorCount")
        self.repeat_floors.setRange(1,200)
        self.repeat_floors.setValue(1)
        self.repeat_floors.setEnabled(False)
        main.addWidget(self.repeat_floors)
        self.only_typical_floor.toggled.connect(self.repeat_floors.setEnabled)
        self.building_floors.valueChanged.connect(self.repeat_floors.setMaximum)
        self._team=None
        self.supervision_count.currentIndexChanged.connect(self._count_changed)
        self.supervision_edit.clicked.connect(self._configure_team)
        self._count_changed()
        main.addWidget(QLabel("وضعیت عملیات پروژه (برای جلوگیری از فعالیت‌های غیرمرتبط):"))
        self.project_kind=QComboBox()
        self.project_kind.setObjectName("DrawingWorkflowProjectKind")
        self.project_kind.addItem("احداث ساختمان جدید","new_build")
        self.project_kind.addItem("بازسازی، بهسازی و مقاوم‌سازی موجود","renovation")
        self.project_kind.addItem("تکمیل و نازک‌کاری ساختمان موجود","fitout")
        main.addWidget(self.project_kind)
        main.addWidget(QLabel("تشخیص اولیه جنس اسکلت از نوشته‌ها و لایه‌های نقشه:"))
        self.frame_kind = QComboBox()
        self.frame_kind.setObjectName("DrawingWorkflowStructureType")
        for code, title in _KIND_LABELS:
            self.frame_kind.addItem(title, code)
        initial = str(evidence.get("kind", "unknown"))
        index = self.frame_kind.findData(initial)
        self.frame_kind.setCurrentIndex(max(0, index))
        main.addWidget(self.frame_kind)
        evidence_rows = list(evidence.get("evidence", []))
        reason = evidence.get("reason", "شواهد نقشه کافی نیست")
        proof = " | ".join(str(x.get("source", "")) + ": " + str(x.get("label", "")) for x in evidence_rows[:3])
        evidence_label = QLabel("وضعیت تشخیص: " + str(evidence.get("confidence", "insufficient"))
                                + "\n" + str(reason) + ("\nشاهد: " + proof if proof else ""))
        evidence_label.setWordWrap(True)
        main.addWidget(evidence_label)
        main.addWidget(QLabel("رشته‌های موردنظر را انتخاب کن (متره سازه بر اساس نوع تأییدشده فعال است):"))
        self.disciplines = {}
        for code, name in _DISCIPLINE_LABELS:
            cb = QCheckBox(name)
            cb.setObjectName("DrawingDiscipline_" + code)
            self.disciplines[code] = cb
            main.addWidget(cb)
        note = QLabel(
            "برنامه زمان‌بندی پیشنهادی هم‌زمان با متره فعال می‌شود. روابط و مدت‌های عرفی "
            "فقط پیش‌نویس قابل ویرایش‌اند؛ تاریخ اتمام، ظرفیت اکیپ و کمیت قطعی حدس زده نمی‌شوند."
        )
        note.setWordWrap(True)
        main.addWidget(note)
        buttons = QHBoxLayout()
        self.begin = QPushButton("تأیید انتخاب‌ها و شروع")
        self.begin.setObjectName("DrawingWorkflowStart")
        self.skip = QPushButton("فعلاً فقط مشاهده نقشه")
        self.skip.setObjectName("DrawingWorkflowViewOnly")
        self.begin.clicked.connect(self._validate_and_accept)
        self.skip.clicked.connect(self.reject)
        buttons.addWidget(self.begin)
        buttons.addWidget(self.skip)
        main.addLayout(buttons)

    def _count_changed(self):
        from core.projects.weekly_ownership import recommended_team
        count=self.supervision_count.currentData() or 1
        names=(["سرپرست کل پروژه"] if count==1 else
               [f"سرپرست {i+1}" for i in range(count)])
        self._team=recommended_team(names)
        self.supervision_summary.setText(" | ".join(
            person["name"]+": "+", ".join(person["trades"])
            for person in self._team["people"]
        ))

    def selected_supervision_team(self):
        from copy import deepcopy
        return deepcopy(self._team)

    def _configure_team(self):
        from core.projects.weekly_ownership import define_team,TRADES
        people=self._team["people"]
        names=[]
        for index,person in enumerate(people):
            name,ok=QInputDialog.getText(
                self,"معرفی سرپرستان",f"نام سرپرست {index+1}:",
                text=person["name"],
            )
            if not ok:return
            names.append(name)
        owners={}
        for discipline in TRADES:
            if len(people)==1:
                owners[discipline]=0
                continue
            choices=[f"{i+1} | {name}" for i,name in enumerate(names)]
            current=self._team["owners"].get(discipline,"supervisor-1")
            initial=max(0,min(len(choices)-1,int(current.rsplit("-",1)[1])-1))
            selected,ok=QInputDialog.getItem(
                self,"تقسیم رشته‌ها","سرپرست مسئول "+discipline+":",
                choices,initial,False
            )
            if not ok:return
            owners[discipline]=choices.index(selected)
        try:
            revised=define_team(names,owners)
        except ValueError as exc:
            QMessageBox.warning(self,"تقسیم مسئولیت",str(exc))
            return
        self._team=revised
        self.supervision_summary.setText(" | ".join(
            person["name"]+": "+", ".join(person["trades"])
            for person in revised["people"]
        ))

    def _choose_project_date(self):
        from core.projects.jalali_dates import gregorian_to_jalali
        picker=QDialog(self)
        picker.setWindowTitle("انتخاب روز آغاز عملیات پروژه")
        picker.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        pane=QVBoxLayout(picker)
        calendar=QCalendarWidget(picker)
        calendar.setObjectName("VisibleProjectStartCalendar")
        calendar.setGridVisible(True)
        current=QDate.currentDate()
        calendar.setSelectedDate(current)
        hint=QLabel(gregorian_to_jalali(current.toPython()))
        calendar.selectionChanged.connect(
            lambda:hint.setText(gregorian_to_jalali(calendar.selectedDate().toPython()))
        )
        pane.addWidget(calendar)
        pane.addWidget(QLabel("پیش‌نمایش شمسی تاریخ انتخابی:"))
        pane.addWidget(hint)
        confirm=QPushButton("تأیید تاریخ شمسی شروع پروژه")
        confirm.clicked.connect(picker.accept)
        pane.addWidget(confirm)
        if picker.exec()==QDialog.DialogCode.Accepted:
            self._selected_start_date=hint.text()
            self.start_date_label.setText("شروع پروژه: "+self._selected_start_date)

    def selected_start_date(self):
        return self._selected_start_date

    def selected_building_scope(self):
        from core.projects.building_scale import building_scope
        return building_scope(
            self.building_floors.value(),
            self.typical_floor_area.value(),
            source_scope=(
                "single_typical_floor" if self.only_typical_floor.isChecked()
                else "whole_building"
            ),
            repeat_floors=(
                self.repeat_floors.value() if self.only_typical_floor.isChecked() else 1
            ),
        )

    def _validate_and_accept(self):
        if self.pricing_mode.currentData() is None or self.automatic_schedule.currentData() is None:
            QMessageBox.warning(self,"انتخاب اولیه نقشه",
                "ابتدا مبنای صورت‌وضعیت و سپس فعال یا غیرفعال‌بودن زمان‌بندی را انتخاب کنید")
            return
        if self.automatic_schedule.currentData()=="yes" and not self._selected_start_date:
            QMessageBox.warning(
                self,"تاریخ شروع پروژه",
                "برای زمان‌بندی خودکار، تاریخ شروع را از تقویم انتخاب کنید"
            )
            return
        if self.automatic_schedule.currentData()=="yes":
            try:
                self.selected_building_scope()
            except ValueError as exc:
                QMessageBox.warning(self,"متراژ و طبقات",str(exc))
                return
        self.accept()

    def pricing_selection(self):
        return self.pricing_mode.currentData(),self.contract_price_entry.currentData()

    def automatic_schedule_selected(self):
        return self.automatic_schedule.currentData()=="yes"

    def selection(self) -> tuple[str, list[str]]:
        return self.frame_kind.currentData(), [
            code for code, cb in self.disciplines.items() if cb.isChecked()
        ]

    def selected_project_kind(self) -> str:
        return self.project_kind.currentData()


class DrawingScheduleDialog(QDialog):
    """Nonmodal editor of relative working-day durations and dependencies."""

    HEADERS = (
        "شناسه WBS", "فعالیت", "رشته", "مدت (روز کاری)", "پیش‌نیازها",
        "اکیپ", "تعداد ردیف متره", "مقدار متره (موقت)", "شروع نسبی", "پایان نسبی",
        "تعداد اکیپ", "ضریب بهره‌وری", "رابطه و تأخیر FS/SS/FF/SF",
        "شروع شمسی", "پایان شمسی",
    )

    def __init__(self, get_plan, on_edit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("برنامه زمان‌بندی هم‌زمان با متره | پیش‌نویس قابل ویرایش")
        self.setObjectName("DrawingLiveScheduleDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1080, 660)
        self.get_plan = get_plan
        self.on_edit = on_edit
        self._rendering = False
        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        controls=QHBoxLayout()
        self.calendar_start=QLineEdit()
        self.calendar_start.setObjectName("WBSJalaliStart")
        self.calendar_start.setPlaceholderText("شروع شمسی ۱۴۰۵ تا ۱۴۱۰، مثل ۱۴۰۷/۰۸/۰۹")
        self.extra_holidays=QLineEdit()
        self.extra_holidays.setObjectName("WBSExtraHolidays")
        self.extra_holidays.setPlaceholderText("تعطیلی محلی یا موردی: ۱۴۰۷/۰۸/۱۱، ...")
        self.apply_calendar_button=QPushButton("اعمال تقویم شمسی")
        self.apply_calendar_button.clicked.connect(self._calendar_changed)
        controls.addWidget(self.calendar_start)
        controls.addWidget(self.extra_holidays)
        controls.addWidget(self.apply_calendar_button)
        layout.addLayout(controls)
        poolbar=QHBoxLayout()
        self.capacity_input=QLineEdit()
        self.capacity_input.setObjectName("WBSResourceCapacities")
        self.capacity_input.setPlaceholderText("اکیپ مشترک=۱, اکیپ دوم=۲")
        self.crew_check=QPushButton("کنترل تداخل اکیپ")
        self.crew_check.clicked.connect(lambda:self._crew_constraints(False))
        self.crew_level=QPushButton("تراز اکیپ (پیشنهادی)")
        self.crew_level.clicked.connect(lambda:self._crew_constraints(True))
        self.add_task=QPushButton("افزودن فعالیت سفارشی")
        self.add_task.clicked.connect(self._add_task)
        self.rate_calibration=QPushButton("ورود راندمان واقعی اکیپ (CSV)")
        self.rate_calibration.setObjectName("ImportObservedProductivityCSV")
        self.rate_calibration.clicked.connect(self._import_site_productivity)
        for w in (self.capacity_input,self.crew_check,self.crew_level,self.add_task,self.rate_calibration):
            poolbar.addWidget(w)
        layout.addLayout(poolbar)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setObjectName("DrawingLiveScheduleTable")
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._changed)
        layout.addWidget(self.table)
        layout.addWidget(QLabel("گانت نسبیِ روزهای کاری: همپوشانی فعالیت‌ها و مدت‌ها (بدون تاریخ قطعی)"))
        self.gantt_scene=QGraphicsScene(self)
        self.gantt_view=QGraphicsView(self.gantt_scene)
        self.gantt_view.setObjectName("DrawingRelativeGantt")
        self.gantt_view.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.gantt_view.setMinimumHeight(215)
        layout.addWidget(self.gantt_view)
        bar = QHBoxLayout()
        self.total = QLabel()
        self.close_button = QPushButton("بستن پنجره (برنامه در نشست محفوظ است)")
        self.close_button.clicked.connect(self.hide)
        bar.addWidget(self.total)
        bar.addWidget(self.close_button)
        layout.addLayout(bar)
        self.refresh()

    @staticmethod
    def _quantity_text(task):
        sums = defaultdict(Decimal)
        for record in task.get("measured", {}).values():
            try:
                qty = Decimal(str(record["quantity"]))
                if not qty.is_finite():
                    raise ValueError("nonfinite")
                sums[str(record["unit"])] += qty
            except (KeyError, InvalidOperation, ValueError):
                return "مقدار نامعتبر؛ بازبینی لازم است"
        return " + ".join(f"{v.normalize()} {unit}" for unit,v in sorted(sums.items())) if sums else "هنوز متره نشده"

    def _render_gantt(self,plan):
        """Bounded relative-working-day visualization, NOT a dated baseline."""
        scene=self.gantt_scene
        scene.clear()
        active=[task for task in plan["tasks"] if task["duration_days"]>0]
        if not active:
            scene.addText("فعالیت زمان‌دار وجود ندارد؛ متره یا مدت تأیید شود")
            scene.setSceneRect(0,0,900,65)
            return
        active=active[:120]
        total=max(1,int(plan.get("indicative_total_workdays",1)))
        step=max(2.0,min(14.0,750.0/total))
        origin_x=225
        y_step=27
        for i,task in enumerate(active):
            y=18+i*y_step
            desc=scene.addText(str(task["title"])[:32])
            desc.setDefaultTextColor(QColor("#66717d"))
            desc.setPos(0,y-6)
            duration=int(task["duration_days"])
            x=origin_x+int(task["start_workday_offset"])*step
            color=("#20745d" if task.get("duration_edited") else
                   "#a96a1e" if task.get("duration_status")=="ESTIMATED_REQUIRES_SITE_REVIEW"
                   else "#406f9b")
            scene.addRect(x,y,max(2,duration*step),14,
                          QPen(Qt.PenStyle.NoPen),QBrush(QColor(color)))
            note=scene.addText(str(duration)+" روز")
            note.setDefaultTextColor(QColor("#66717d"))
            note.setPos(x+duration*step+3,y-8)
        scene.setSceneRect(0,0,origin_x+total*step+100,35+len(active)*y_step)

    def refresh(self):
        plan = self.get_plan()
        if not plan or self._rendering:
            return
        self._rendering = True
        self.table.blockSignals(True)
        try:
            self.note.setText(
                "پیش‌نویس غیرمصوب، بدون تاریخ شروع و بدون ادعای مسیر بحرانی قطعی. "
                + str(plan.get("assumption_note", "")) + "\n"
                + "تغییر عنوان، مدت، پیش‌نیاز و اکیپ مجاز است. "
                "برای پیش‌نیاز چندگانه شناسه‌ها را با ویرگول جدا کن."
            )
            tasks = plan["tasks"]
            self.table.setRowCount(len(tasks))
            for row, task in enumerate(tasks):
                cols = (
                    task["id"], task["title"], task["discipline"],
                    str(task["duration_days"]), ", ".join(task["predecessors"]),
                    task["crew"], str(len(task["linked_item_ids"])),
                    self._quantity_text(task),
                    str(task["start_workday_offset"]), str(task["end_workday_offset"]),
                    str(task.get("crew_count","")),str(task.get("efficiency","1")),
                    "; ".join(
                        f"{l['predecessor']}:{l['type']}:{l['lag_days']}"
                        for l in task.get("links",[])
                    ),
                    task.get("start_jalali",""),task.get("finish_jalali",""),
                )
                for col, val in enumerate(cols):
                    cell = QTableWidgetItem(val)
                    if col not in (1, 3, 4, 5, 10, 11, 12):
                        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 3 and task.get("duration_edited"):
                        cell.setToolTip("مدت توسط کاربر اصلاح شده و با به‌روزرسانی متره بازنویسی نمی‌شود")
                    if col == 7:
                        cell.setToolTip("مقدار فقط از ردیف‌های متره مرتبط آمده و تا بازبینی منبع، قطعی نیست")
                    self.table.setItem(row, col, cell)
            self._render_gantt(plan)
            conflicts=plan.get("resource_conflicts",[])
            self.total.setText(
                "مدت شبکه پیشنهادی: " + str(plan.get("indicative_total_workdays", 0))
                + " روز کاری نسبی | بدون تاریخ قطعی"
                + " | ردیف‌های متره فاقد تطبیق: "
                + str(len(plan.get("unassigned_item_ids", [])))
                + " | تداخل اکیپ: "+str(len(conflicts))
                + (" | پایان شمسی پیشنهادی: "+plan["scheduled_end_jalali"]
                   if plan.get("scheduled_end_jalali") else "")
            )
        finally:
            self.table.blockSignals(False)
            self._rendering = False

    def _calendar_changed(self):
        from core.projects.iran_worksite_calendar import make_calendar,calendarize
        value=self.calendar_start.text().strip()
        extra=[v.strip() for v in self.extra_holidays.text().replace("،",",").split(",") if v.strip()]
        try:
            if not value:raise ValueError("تاریخ شروع شمسی از ۱۴۰۵ تا ۱۴۱۰ را وارد کنید")
            output=calendarize(self.get_plan(),make_calendar(
                start_date=value,extra_holidays=extra,
            ))
            self.on_edit(output)
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"تقویم پروژه",str(exc))
        self.refresh()

    def _crew_constraints(self,level):
        from core.drawings.workflow_planning import apply_resource_limits
        try:
            limits={}
            for pair in self.capacity_input.text().replace("،",",").split(","):
                if not pair.strip():continue
                if "=" not in pair:raise ValueError("قالب ظرفیت: نام اکیپ=تعداد")
                key,value=pair.split("=",1)
                key=key.strip()
                if not key or key in limits:raise ValueError("نام اکیپ باید یکتا باشد")
                limits[key]=int(value.strip())
            plan=apply_resource_limits(self.get_plan(),limits,level=level)
            self.on_edit(plan)
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"کنترل اکیپ‌ها",str(exc))
        self.refresh()

    def _import_site_productivity(self):
        import csv
        from pathlib import Path
        from core.projects.production_catalog import CATALOG
        from core.projects.productivity_evidence import calibrate_productivity
        from core.drawings.workflow_planning import register_project_productivity_calibration
        plan=self.get_plan()
        if not plan.get("project_id"):
            QMessageBox.warning(self,"راندمان واقعی","ابتدا برنامه را به یک پروژه واقعی ذخیره‌شده متصل کنید")
            return
        available=[t["id"] for t in plan["tasks"] if t["id"] in CATALOG]
        profile,yes=QInputDialog.getItem(
            self,"فعالیت مبنای راندمان","فعالیت مورد مشاهده:",
            available,0,False,
        )
        if not yes:return
        path=QFileDialog.getOpenFileName(
            self,"فایل مشاهدات کارگاه",
            "","فایل مشاهدات CSV (*.csv)",
        )[0]
        if not path:return
        reviewer,yes=QInputDialog.getText(
            self,"بازبینی راندمان","نام مهندس بازبین شواهد کارگاه:"
        )
        if not yes:return
        try:
            file=Path(path)
            if file.stat().st_size>3*1024*1024:
                raise ValueError("فایل مشاهدات بزرگ‌تر از حد مجاز است")
            with file.open("r",encoding="utf-8-sig",newline="") as stream:
                reader=csv.DictReader(stream)
                cols={"observed_on","quantity","unit","workdays","crews","source_path"}
                if not cols.issubset(reader.fieldnames or []):
                    raise ValueError("ستون‌های لازم CSV موجود نیست")
                rows=[]
                for row in reader:
                    if len(rows)>=100:raise ValueError("حداکثر ۱۰۰ مشاهده در هر فایل")
                    ref=Path(row["source_path"])
                    row["source_path"]=str(ref if ref.is_absolute() else file.parent/ref)
                    rows.append(row)
            evidence=calibrate_productivity(profile,rows,reviewer=reviewer,
                     project_id=plan["project_id"])
            revised=register_project_productivity_calibration(plan,evidence)
            self.on_edit(revised)
        except (ValueError,TypeError,OSError,UnicodeError) as exc:
            QMessageBox.warning(self,"کالیبراسیون راندمان",str(exc))
        self.refresh()

    def _add_task(self):
        from core.drawings.workflow_planning import add_custom_activity
        name,ok=QInputDialog.getText(self,"WBS سفارشی","عنوان فعالیت جدید:")
        if not ok:return
        scope,ok=QInputDialog.getItem(
            self,"رشته فعالیت","رشته جدید:",
            list(self.get_plan().get("disciplines",[])),0,False,
        )
        if not ok:return
        try:
            self.on_edit(add_custom_activity(self.get_plan(),name,scope))
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"افزودن فعالیت",str(exc))
        self.refresh()

    def _changed(self, cell):
        if self._rendering or cell.column() not in (1, 3, 4, 5, 10, 11, 12):
            return
        plan = self.get_plan()
        if not plan or cell.row() >= len(plan["tasks"]):
            return
        task_id = plan["tasks"][cell.row()]["id"]
        text = cell.text().strip()
        try:
            if cell.column() == 1:
                revised = edit_activity(plan, task_id, title=text)
            elif cell.column() == 3:
                revised = edit_activity(plan, task_id, duration_days=int(text))
            elif cell.column() == 4:
                predecessor_ids = [v.strip() for v in text.split(",") if v.strip()]
                revised = edit_activity(plan, task_id, predecessors=predecessor_ids)
            elif cell.column() == 5:
                revised = edit_activity(plan, task_id, crew=text)
            elif cell.column() == 10:
                revised = edit_activity(plan, task_id, crew_count=int(text))
            elif cell.column() == 11:
                revised = edit_activity(plan, task_id, efficiency=text)
            else:
                links=[]
                for token in text.split(";"):
                    if not token.strip():continue
                    parts=[v.strip() for v in token.split(":")]
                    if len(parts)!=3:raise ValueError("فرمت رابطه: شناسه:FS/SS/FF/SF:تاخیر")
                    links.append({
                        "predecessor":parts[0],"type":parts[1],
                        "lag_days":int(parts[2]),
                    })
                revised = edit_activity(
                    plan,task_id,predecessors=[x["predecessor"] for x in links],
                    links=links,
                )
            self.on_edit(revised)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "ویرایش برنامه زمان‌بندی", str(exc))
        self.refresh()
