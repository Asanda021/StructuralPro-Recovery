"""Read-only, user-run PDF column length/steel scenario inside the Qt review UI.

No database, project takeoff, financial summary or BOQ mutation is possible here.
Every weight factor is an editable scenario input, not a PDF extraction.
"""
from __future__ import annotations

from pathlib import Path
import json
from hashlib import sha256

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
)

from core.drawings.pdf_column_length_schedule import draft_column_length_schedule, write_schedule
from core.drawings.pdf_column_weight_preview import (
    draft_component_weight_preview, write_weight_preview, export_weight_preview_xlsx,
)


class PDFColumnTakeoffPanel(QWidget):
    """A PDF-source-backed, clearly *nonfinancial* engineering worksheet."""
    INPUT_FIELDS = ('profile_name', 'profile_count', 'profile_unit_mass_kg_m',
                    'plate_count', 'plate_length_mm', 'plate_width_mm',
                    'plate_thickness_mm', 'steel_density_kg_m3')

    def __init__(self, source_paths=None, parent=None):
        super().__init__(parent)
        self.setObjectName('PDFColumnTakeoffPanel')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.pdf_path = None
        if source_paths and len(source_paths) == 1:
            only = next(iter(source_paths.values()))
            if str(only).lower().endswith('.pdf'):
                self.pdf_path = str(only)
        self.schedule = None
        self.weight_preview = None
        layout = QVBoxLayout(self)
        warning = QLabel('متره آزمایشی ستون | پلان و طول چاپی تیپ‌ها از PDF استخراج می‌شوند. '
                         'تعداد پروفیل، جرم واحد طول و مشخصات ورق، ورودی فرضی کاربرند. '
                         'هیچ‌کدام مجوز متره قطعی، تأیید نقشه، BOQ یا صورت‌وضعیت نیستند.')
        warning.setObjectName('PDFColumnDraftWarning')
        warning.setWordWrap(True)
        layout.addWidget(warning)
        buttons = QHBoxLayout()
        self.choose_button = QPushButton('انتخاب PDF دیگر')
        self.choose_button.setObjectName('PDFColumnChooseSource')
        self.choose_button.clicked.connect(self._pick_pdf)
        buttons.addWidget(self.choose_button)
        self.extract_button = QPushButton('۱. استخراج ستون‌ها از PDF')
        self.extract_button.setObjectName('PDFColumnExtract')
        self.extract_button.clicked.connect(self.extract)
        buttons.addWidget(self.extract_button)
        layout.addLayout(buttons)
        self.receipt = QLabel('فایل PDF را انتخاب و استخراج را اجرا کنید.')
        self.receipt.setObjectName('PDFColumnTakeoffReceipt')
        self.receipt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.receipt.setWordWrap(True)
        layout.addWidget(self.receipt)

        self.positions = QTableWidget(0, 6, self)
        self.positions.setObjectName('PDFColumnSourcePositions')
        self.positions.setHorizontalHeaderLabels(['شناسه PDF','تقاطع','تیپ','طول چاپی (m)','مختصات (pt)','وضعیت'])
        self.positions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.positions)

        self.assumptions = QTableWidget(0, 11, self)
        self.assumptions.setObjectName('PDFColumnSteelAssumptions')
        self.assumptions.setHorizontalHeaderLabels([
            'تیپ','تعداد موقعیت','طول فرضی کل m','نام پروفیل (فرض)',
            'پروفیل/ستون (فرض)','kg/m (فرض)','ورق/ستون (فرض)',
            'طول ورق mm','عرض ورق mm','ضخامت ورق mm','چگالی kg/m³ (فرض)',
        ])
        self.assumptions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.assumptions)
        self.scenario_ack = QCheckBox('می‌پذیرم که ضرایب و ورق‌های واردشده فرض سناریویی هستند و از PDF تأیید نشده‌اند.')
        self.scenario_ack.setObjectName('PDFColumnScenarioAcknowledgment')
        layout.addWidget(self.scenario_ack)
        row = QHBoxLayout()
        self.weight_button = QPushButton('۲. محاسبه سناریوی وزن پروفیل و ورق')
        self.weight_button.setObjectName('PDFColumnComputeSteel')
        self.weight_button.clicked.connect(self.compute_weight)
        self.weight_button.setEnabled(False)
        row.addWidget(self.weight_button)
        self.export_button = QPushButton('۳. خروجی Excel / CSV / JSON')
        self.export_button.setObjectName('PDFColumnExport')
        self.export_button.clicked.connect(self.export)
        self.export_button.setEnabled(False)
        row.addWidget(self.export_button)
        layout.addLayout(row)
        self.weight_receipt = QLabel('وزن صفر نیست؛ وزن محاسبه نشده است. ابتدا فرض‌ها را بررسی کنید.')
        self.weight_receipt.setObjectName('PDFColumnWeightReceipt')
        self.weight_receipt.setWordWrap(True)
        layout.addWidget(self.weight_receipt)
        self.weight_rows = QTableWidget(0, 5, self)
        self.weight_rows.setObjectName('PDFColumnWeightRows')
        self.weight_rows.setHorizontalHeaderLabels(['تیپ','تعداد','جرم پروفیل kg','جرم ورق kg','جرم کل سناریو kg'])
        self.weight_rows.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.weight_rows)

    def _pick_pdf(self):
        filename, _ = QFileDialog.getOpenFileName(self,'انتخاب فایل نقشه PDF','','PDF (*.pdf)')
        if filename:
            self.pdf_path = filename
            self._reset()
            self.receipt.setText('PDF جدید انتخاب شد. برای بررسی دوباره، استخراج را اجرا کنید.')

    def _reset(self):
        self.schedule = self.weight_preview = None
        self.positions.setRowCount(0)
        self.assumptions.setRowCount(0)
        self.weight_rows.setRowCount(0)
        self.scenario_ack.setChecked(False)
        self.weight_button.setEnabled(False)
        self.export_button.setEnabled(False)

    @staticmethod
    def _read_only(value):
        cell = QTableWidgetItem(str(value if value is not None else ''))
        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return cell

    def extract(self):
        if not self.pdf_path or not Path(self.pdf_path).is_file():
            QMessageBox.warning(self,'فایل نقشه','یک فایل PDF موجود انتخاب کنید.')
            return
        self._reset()
        try:
            schedule=draft_column_length_schedule(self.pdf_path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.receipt.setText('استخراج ناموفق: '+str(exc))
            return
        self.schedule = schedule
        if not schedule.get('rows'):
            self.receipt.setText('هیچ ردیف قابل‌استناد: '+schedule.get('status','نامعلوم'))
            return
        rows=schedule['rows']
        self.positions.setRowCount(len(rows))
        for i,r in enumerate(rows):
            data=(r.get('candidate_id'),f"{r.get('grid_row')}/{r.get('grid_column')}",
                  r.get('type_tag'),r.get('printed_length_m'),
                  f"{r.get('x_pt')}, {r.get('y_pt')}",r.get('status'))
            for j,x in enumerate(data):
                self.positions.setItem(i,j,self._read_only(x))
        self.assumptions.setRowCount(len(schedule.get('groups',())))
        for i,group in enumerate(schedule.get('groups',())):
            # Scenario input defaults are DEMONSTRATION assumptions, NEVER read from the PDF.
            data=(group['type_tag'],group['grid_location_candidates'],group['draft_extended_length_m'],
                  'IPE16 (فرض)','2','15.8','0','','','','7850')
            for j,value in enumerate(data):
                cell=QTableWidgetItem(str(value))
                if j<3:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.assumptions.setItem(i,j,cell)
        self.receipt.setText(
            f"{schedule['status']} | PDF SHA256: {schedule['document_sha256']} | "
            f"{schedule.get('grid_node_count')} تقاطع | {schedule.get('draft_node_count')} تیپ خوانده‌شده | "
            f"طول سناریویی {schedule.get('draft_extended_length_total_m')} متر | "
            'بدون تأیید Revision، تعداد تکرار طبقات یا پرداخت مالی'
        )
        self.weight_button.setEnabled(bool(schedule.get('groups')))
        self.export_button.setEnabled(bool(schedule.get('groups')))

    def _source_unchanged(self):
        if not self.pdf_path or not self.schedule:
            return False
        try:
            return sha256(Path(self.pdf_path).read_bytes()).hexdigest() == self.schedule['document_sha256']
        except OSError:
            return False

    def compute_weight(self):
        if self.schedule is None or not self.schedule.get('groups'):
            return
        if not self._source_unchanged():
            self.weight_receipt.setText('فایل PDF پس از استخراج تغییر کرده یا در دسترس نیست؛ دوباره استخراج کنید.')
            self.weight_preview = None
            return
        if not self.scenario_ack.isChecked():
            QMessageBox.warning(self,'فرض‌های وزن','ابتدا فرضی‌بودن ضرایب سناریو را تأیید کنید.')
            return
        scenarios={}
        for i in range(self.assumptions.rowCount()):
            tag=self.assumptions.item(i,0).text()
            entries=[self.assumptions.item(i,j).text().strip() if self.assumptions.item(i,j) else ''
                     for j in range(3,11)]
            spec=dict(zip(self.INPUT_FIELDS,entries))
            if not spec['plate_count']:
                spec['plate_count']='0'
            scenarios[tag]=spec
        try:
            preview=draft_component_weight_preview(self.schedule,scenarios)
        except ValueError as exc:
            self.weight_receipt.setText('ورودی وزن نامعتبر: '+str(exc))
            self.weight_preview=None
            return
        self.weight_preview=preview
        self.weight_rows.setRowCount(len(preview['groups']))
        for i,r in enumerate(preview['groups']):
            for j,x in enumerate((r['type_tag'],r['grid_location_candidates'],r['profile_mass_kg'],
                                  r['plate_mass_kg'],r['estimated_total_kg'])):
                self.weight_rows.setItem(i,j,self._read_only(x))
        self.weight_receipt.setText(
            f"جرم فرضی پروفیل: {preview['profile_mass_total_kg']} kg | "
            f"جرم فرضی ورق‌های واردشده: {preview['plate_mass_total_kg']} kg | "
            f"جمع سناریو: {preview['draft_weight_total_kg']} kg. "
            'بدون ورق‌های ثبت‌نشده، جوش، پیچ، وصله و پرت. غیرمالی و تأییدنشده.'
        )

    def export(self):
        if self.schedule is None or not self.schedule.get('groups'):
            return
        if not self._source_unchanged():
            self.weight_preview = None
            self.weight_receipt.setText('PDF منبع تغییر کرده است؛ خروجی قدیمی مجاز نیست. دوباره استخراج کنید.')
            return
        name, selected = QFileDialog.getSaveFileName(
            self,'ذخیره متره آزمایشی ستون','column_type_weight_preview.xlsx',
            'Excel (*.xlsx);;CSV (*.csv);;JSON (*.json)')
        if not name:
            return
        path=Path(name)
        if path.suffix.lower() not in ('.xlsx','.csv','.json'):
            QMessageBox.warning(self,'پسوند نامعتبر','فایل خروجی باید xlsx، csv یا json باشد.')
            return
        if self.weight_preview is None:
            QMessageBox.warning(self,'محاسبه وزن','ابتدا سناریوی وزن را با فرض‌های تأییدشده محاسبه کنید.')
            return
        try:
            if path.suffix.lower()=='.xlsx':
                export_weight_preview_xlsx(self.schedule,self.weight_preview,path)
            elif path.suffix.lower()=='.csv':
                write_weight_preview(self.weight_preview,json_path=path.with_suffix('.json'),csv_path=path)
            else:
                path.write_text(json.dumps({'source_schedule':self.schedule,'weight_scenario':self.weight_preview},
                                           ensure_ascii=False,indent=2),encoding='utf-8')
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self,'خطای خروجی',str(exc))
            return
        QMessageBox.information(self,'متره آزمایشی','فایل غیرمالی ذخیره شد؛ هیچ مبلغ یا BOQ تغییر نکرد.')