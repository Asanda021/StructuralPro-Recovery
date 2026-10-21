"""Persian Qt editor for explicitly reviewed longitudinal stirrup zones."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QHeaderView,
)
from core.takeoff.stirrup_zones import validate_stirrup_zones

_FIELDS = (
    ("name", "نام ناحیه"), ("start_m", "شروع (متر)"),
    ("end_m", "پایان (متر)"), ("spacing_m", "گام (متر)"),
    ("first_bar_m", "اولین خاموت (متر)"), ("last_bar_m", "آخرین خاموت (متر)"),
    ("count", "تعداد واقعی"), ("cut_length_m", "طول برش (متر)"),
    ("unit_weight_kg_m", "وزن واحد (کیلوگرم/متر)"),
    ("unit_weight_source", "مرجع وزن واحد خاموت"),
    ("source_ref", "مرجع دیتایل"),
    ('id','شناسه مستقل خاموت'),('nominal_diameter_mm','قطر (میلی‌متر)'),('shape_kind','شکل؛ مستطیلی'),('shape_ref','مرجع شکل'),('section_width_m','عرض بیرونی خاموت (متر)'),('section_depth_m','ارتفاع بیرونی خاموت (متر)'),('section_ref','مرجع ابعاد خاموت'),('cut_length_ref','مرجع طول برش شامل خم و قلاب'),
)


class StirrupZoneEditor(QDialog):
    """Only verified zones leave this dialog; no count estimation or approval."""

    def __init__(self, *, beam_length_m: float, zones: list[dict] | None = None, specialist=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ویرایش نواحی خاموت تیر")
        self.resize(1250, 510)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.beam_length_m = beam_length_m
        self.specialist=specialist
        self.zones: list[dict] | None = None
        root = QVBoxLayout(self)
        guide = QLabel(
            "همه فاصله‌ها از ابتدای همین تیر و برحسب متر هستند. مرز نواحی باید کل طول تیر را "
            "بدون هم‌پوشانی بپوشاند؛ محل اولین و آخرین خاموت و تعداد واقعی را از دیتایل وارد کنید. "
            "طول برش باید شامل خم و قلاب تأییدشده باشد؛ محاسبه از گام به‌تنهایی ممنوع است."
        )
        guide.setWordWrap(True)
        root.addWidget(guide)
        self.table = QTableWidget(0, len(_FIELDS))
        self.table.setHorizontalHeaderLabels([label for _, label in _FIELDS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table)
        actions = QHBoxLayout()
        self.add_button = QPushButton("افزودن ناحیه")
        self.remove_button = QPushButton("حذف ناحیه انتخابی")
        self.save_button = QPushButton("بررسی و انتقال به پیش‌نویس")
        self.cancel_button = QPushButton("انصراف")
        for item in (self.add_button, self.remove_button, self.save_button, self.cancel_button):
            actions.addWidget(item)
        root.addLayout(actions)
        self.add_button.clicked.connect(self.add_zone)
        self.remove_button.clicked.connect(self.remove_selected)
        self.save_button.clicked.connect(self.accept_validated)
        self.cancel_button.clicked.connect(self.reject)
        for zone in (zones or []):
            self.add_zone(zone)

    def add_zone(self, zone: dict | None = None):
        # New rows remain EMPTY: the program must not fabricate geometry or quantities.
        zone = zone if isinstance(zone, dict) else {}
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, (key, _) in enumerate(_FIELDS):
            value = zone.get(key, "")
            if key=="shape_kind" and value=="rectangular":value="مستطیلی"
            self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.selectRow(row)

    def remove_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "ناحیه خاموت", "ناحیه‌ای برای حذف انتخاب نشده است")
            return
        self.table.removeRow(row)

    def collect_rows(self) -> list[dict]:
        values = []
        for index in range(self.table.rowCount()):
            row = {}
            for col, (key, _) in enumerate(_FIELDS):
                item = self.table.item(index, col)
                row[key] = item.text().strip() if item is not None else ""
            values.append(row)
        return values

    def accept_validated(self):
        try:
            raw=self.collect_rows();self.zones=validate_stirrup_zones(raw,self.beam_length_m)
            if self.specialist:
                for z in raw:z['shape_kind']={'مستطیلی':'rectangular','rectangular':'rectangular'}.get(z['shape_kind'],z['shape_kind'])
                raw.sort(key=lambda z:float(z['start_m']))
                self.zones=raw
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "دیتایل خاموت ناقص یا نامعتبر", str(exc))
            return
        super().accept()
