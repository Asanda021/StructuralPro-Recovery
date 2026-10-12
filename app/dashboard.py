"""Professional, compact StructuralPro dashboard for the Windows desktop shell."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QScrollArea, QMessageBox
)


def _card(title: str, value: str, hint: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("KpiCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(5)
    title_label = QLabel(title)
    title_label.setObjectName("KpiTitle")
    value_label = QLabel(value)
    value_label.setObjectName("KpiValue")
    hint_label = QLabel(hint)
    hint_label.setObjectName("KpiHint")
    hint_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addWidget(hint_label)
    return frame


def _section(title: str, description: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("DashboardSection")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("SectionTitle")
    layout.addWidget(heading)
    if description:
        desc = QLabel(description)
        desc.setObjectName("SectionDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)
    return frame, layout


class DashboardPage(QWidget):
    """Project-first dashboard: concise KPIs, clear workflow, real project data."""

    def __init__(self, service, catalog, on_open_page=None):
        super().__init__()
        self.service = service
        self.catalog = catalog
        self.on_open_page = on_open_page
        self._build()
        self.refresh()

    def _open(self, index: int):
        if self.on_open_page:
            self.on_open_page(index)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(0, 0, 8, 0)
        root.setSpacing(14)

        title = QLabel("داشبورد پروژه")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "نمای سریع وضعیت پروژه، هزینه، پیشرفت و دسترسی مستقیم به گردش‌کار اصلی StructuralPro."
        )
        subtitle.setObjectName("PageDescription")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        workflow, wv = _section(
            "گردش‌کار اصلی",
            "هر بخش یک پنجره مشخص دارد؛ از اینجا مستقیماً وارد مرحله موردنظر شوید."
        )
        buttons = QGridLayout()
        buttons.setHorizontalSpacing(10)
        buttons.setVerticalSpacing(10)
        actions = [
            ("➕ پروژه جدید", 1),
            ("📐 متره", 3),
            ("📋 BOQ و برآورد", 5),
            ("💰 فهرست‌بها", 4),
            ("🧾 صورت‌وضعیت", 6),
            ("📊 گزارش‌ها", 7),
            ("📁 اسناد پروژه", 8),
            ("🤖 هوش مصنوعی", 11),
        ]
        for i, (label, index) in enumerate(actions):
            button = QPushButton(label)
            button.setObjectName("DashboardAction")
            button.setMinimumHeight(48)
            button.clicked.connect(lambda _=False, idx=index: self._open(idx))
            buttons.addWidget(button, i // 4, i % 4)
        wv.addLayout(buttons)
        root.addWidget(workflow)

        kpi_section, kv = _section("وضعیت سریع")
        self.cards = QGridLayout()
        self.cards.setHorizontalSpacing(12)
        self.cards.setVerticalSpacing(12)
        kv.addLayout(self.cards)
        root.addWidget(kpi_section)

        financial, fv = _section("خلاصه مالی پروژه")
        self.financial_summary = QLabel("برای مشاهده اطلاعات مالی، پروژه‌ای ایجاد یا انتخاب کنید.")
        self.financial_summary.setObjectName("DashboardSummary")
        self.financial_summary.setWordWrap(True)
        fv.addWidget(self.financial_summary)
        root.addWidget(financial)

        projects_section, pv = _section("پروژه‌های اخیر", "پروژه را انتخاب کنید تا وارد گردش‌کار آن شوید.")
        self.project_selector = QComboBox()
        self.project_selector.setMinimumHeight(40)
        self.project_selector.currentIndexChanged.connect(self._refresh_selected_project)
        pv.addWidget(self.project_selector)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["شناسه", "نام پروژه", "وضعیت"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(220)
        pv.addWidget(self.table)
        root.addWidget(projects_section)

        self.notice = QLabel()
        self.notice.setObjectName("DashboardNotice")
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)

        root.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)

    def _refresh_selected_project(self):
        project_id = self.project_selector.currentData()
        if not project_id:
            self.financial_summary.setText("هنوز پروژه‌ای انتخاب نشده است.")
            return
        try:
            d = self.service.financial_dashboard(project_id)
            receipts = self.service.project_receipt_summary(project_id)
            commitments = self.service.project_commitment_summary(project_id)
            self.financial_summary.setText(
                f"قرارداد/برآورد: {d['contract_amount']:,.0f} | "
                f"کارکرد تجمعی: {d['cumulative_work']:,.0f} | "
                f"پیشرفت: {d['progress_percent']:.1f}% | "
                f"هزینه واقعی: {d['actual_cost']:,.0f} | "
                f"دریافتی: {receipts['total_received']:,.0f} | "
                f"تعهدات: {commitments['committed_total']:,.0f} | "
                f"مطالبات تقریبی: {max(float(d['contract_amount']) - float(receipts['total_received']), 0):,.0f}"
            )
            self.notice.setText(
                f"🟢 پروژه فعال: {project_id} | "
                f"{d['line_count']} ردیف BOQ | آخرین دوره صورت‌وضعیت: {d['latest_statement_no']}"
            )
        except Exception as exc:
            self.financial_summary.setText("اطلاعات مالی این پروژه هنوز قابل محاسبه نیست.")
            self.notice.setText(f"⚠️ کنترل مالی پروژه نیازمند بررسی است: {exc}")

    def refresh(self):
        projects = self.service.store.list()

        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cards = [
            ("پروژه‌ها", str(len(projects)), "پروژه‌های ذخیره‌شده"),
            ("فهرست‌بها", str(len(self.catalog.years())), "سال‌های قابل انتخاب"),
            ("متره", "فعال", "PDF / DXF / DWG / IFC"),
            ("حالت اجرا", "آفلاین", "داده‌ها روی سیستم ذخیره می‌شوند"),
        ]
        for i, data in enumerate(cards):
            self.cards.addWidget(_card(*data), 0, i)

        self.project_selector.blockSignals(True)
        self.project_selector.clear()
        for project in projects:
            self.project_selector.addItem(
                f"{project.get('name', 'بدون نام')} — {project.get('id', '')}",
                project.get("id", ""),
            )
        self.project_selector.blockSignals(False)

        self.table.setRowCount(0)
        for i, project in enumerate(projects[-8:][::-1]):
            self.table.insertRow(i)
            project_id = project.get("id", "")
            status = "آماده"
            try:
                dash = self.service.financial_dashboard(project_id)
                status = f"پیشرفت {dash['progress_percent']:.1f}% | دوره {dash['latest_statement_no']}"
            except Exception:
                pass
            for j, value in enumerate([project_id, project.get("name", ""), status]):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

        if projects:
            self.project_selector.setCurrentIndex(len(projects) - 1)
            self._refresh_selected_project()
        else:
            self.financial_summary.setText(
                "هنوز پروژه‌ای وجود ندارد. از «پروژه جدید» شروع کنید."
            )
            self.notice.setText("⚪ پروژه‌ای برای نمایش در داشبورد وجود ندارد.")
