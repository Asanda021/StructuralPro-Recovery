"""Persian, non-blocking drawing intake and editable schedule workbench.

Keeps the CAD canvas available. All detected structural types and initial
durations are preliminary proposals requiring explicit human review.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView,
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
)


class DrawingWorkflowIntakeDialog(QDialog):
    def __init__(self, source_name: str, evidence: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("پس از بازکردن نقشه | چه کاری انجام دهیم؟")
        self.setObjectName("DrawingWorkflowIntakeDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(610, 510)
        main = QVBoxLayout(self)
        intro = QLabel("از این نقشه چه می‌خواهید؟ ابتدا نوع اسکلت را بررسی کن و رشته‌های متره را انتخاب کن.")
        intro.setWordWrap(True)
        main.addWidget(intro)
        main.addWidget(QLabel("فایل: " + source_name))
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
        self.begin = QPushButton("شروع متره و برنامه زمان‌بندی")
        self.begin.setObjectName("DrawingWorkflowStart")
        self.skip = QPushButton("فعلاً فقط مشاهده نقشه")
        self.skip.setObjectName("DrawingWorkflowViewOnly")
        self.begin.clicked.connect(self.accept)
        self.skip.clicked.connect(self.reject)
        buttons.addWidget(self.begin)
        buttons.addWidget(self.skip)
        main.addLayout(buttons)

    def selection(self) -> tuple[str, list[str]]:
        return self.frame_kind.currentData(), [
            code for code, cb in self.disciplines.items() if cb.isChecked()
        ]


class DrawingScheduleDialog(QDialog):
    """Nonmodal editor of relative working-day durations and dependencies."""

    HEADERS = (
        "شناسه WBS", "فعالیت", "رشته", "مدت (روز کاری)", "پیش‌نیازها",
        "اکیپ", "تعداد ردیف متره", "شروع نسبی", "پایان نسبی",
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
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setObjectName("DrawingLiveScheduleTable")
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._changed)
        layout.addWidget(self.table)
        bar = QHBoxLayout()
        self.total = QLabel()
        self.close_button = QPushButton("بستن پنجره (برنامه در نشست محفوظ است)")
        self.close_button.clicked.connect(self.hide)
        bar.addWidget(self.total)
        bar.addWidget(self.close_button)
        layout.addLayout(bar)
        self.refresh()

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
                    str(task["start_workday_offset"]), str(task["end_workday_offset"]),
                )
                for col, val in enumerate(cols):
                    cell = QTableWidgetItem(val)
                    if col not in (1, 3, 4, 5):
                        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 3 and task.get("duration_edited"):
                        cell.setToolTip("مدت توسط کاربر اصلاح شده و با به‌روزرسانی متره بازنویسی نمی‌شود")
                    self.table.setItem(row, col, cell)
            self.total.setText(
                "مدت شبکه پیشنهادی: " + str(plan.get("indicative_total_workdays", 0))
                + " روز کاری نسبی | بدون تاریخ قطعی"
                + " | ردیف‌های متره فاقد تطبیق: "
                + str(len(plan.get("unassigned_item_ids", [])))
            )
        finally:
            self.table.blockSignals(False)
            self._rendering = False

    def _changed(self, cell):
        if self._rendering or cell.column() not in (1, 3, 4, 5):
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
            else:
                revised = edit_activity(plan, task_id, crew=text)
            self.on_edit(revised)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "ویرایش برنامه زمان‌بندی", str(exc))
        self.refresh()
