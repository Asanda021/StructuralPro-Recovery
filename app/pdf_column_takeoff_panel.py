"""Read-only, user-run PDF column length/steel scenario inside the Qt review UI.

No database, project takeoff, financial summary or BOQ mutation is possible here.
Every weight factor is an editable scenario input, not a PDF extraction.
"""
from __future__ import annotations

from pathlib import Path
import json
from hashlib import sha256

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QAbstractItemView, QPlainTextEdit,
)

from core.drawings.pdf_column_length_schedule import draft_column_length_schedule
from core.drawings.pdf_column_weight_preview import (
    draft_component_weight_preview, write_weight_preview, export_weight_preview_xlsx,
)


class PDFColumnTakeoffPanel(QWidget):
    """A PDF-source-backed, clearly *nonfinancial* engineering worksheet."""
    INPUT_FIELDS = ('profile_name', 'profile_count', 'profile_unit_mass_kg_m',
                    'plate_count', 'plate_length_mm', 'plate_width_mm',
                    'plate_thickness_mm', 'steel_density_kg_m3')
    NO_WEIGHT = 'وزن محاسبه نشده است. ابتدا فرض‌ها را بررسی کنید.'

    def __init__(self, source_paths=None, parent=None, *, expected_sha256=None):
        super().__init__(parent)
        self.setObjectName('PDFColumnTakeoffPanel')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.pdf_path = None
        self._expected_sha256 = None
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
        self.choose_button = QPushButton('انتخاب PDF')
        self.choose_button.setObjectName('PDFColumnChooseSource')
        self.choose_button.clicked.connect(self._pick_pdf)
        buttons.addWidget(self.choose_button)
        self.extract_button = QPushButton('۱. استخراج ستون‌ها از PDF')
        self.extract_button.setObjectName('PDFColumnExtract')
        self.extract_button.clicked.connect(self.extract)
        buttons.addWidget(self.extract_button)
        layout.addLayout(buttons)
        self.source_label = QLabel()
        self.source_label.setObjectName('PDFColumnSourcePath')
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)
        self.receipt = QLabel()
        self.receipt.setObjectName('PDFColumnTakeoffReceipt')
        self.receipt.setTextFormat(Qt.TextFormat.PlainText)
        self.receipt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.receipt.setWordWrap(True)
        layout.addWidget(self.receipt)

        self.positions = QTableWidget(0, 6, self)
        self.positions.setObjectName('PDFColumnSourcePositions')
        self.positions.setHorizontalHeaderLabels(['شناسه PDF','تقاطع','تیپ','طول چاپی (m)','مختصات (pt)','وضعیت'])
        self.positions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.positions.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.positions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.positions)
        self.position_evidence = QPlainTextEdit()
        self.position_evidence.setObjectName('PDFColumnPositionEvidence')
        self.position_evidence.setReadOnly(True)
        self.position_evidence.setMaximumHeight(92)
        self.position_evidence.setPlaceholderText('برای مشاهدهٔ شیت‌ها و عملگرهای شاهد، ردیف موقعیت را انتخاب کنید.')
        self.positions.currentCellChanged.connect(self._position_changed)
        layout.addWidget(self.position_evidence)

        self.assumptions = QTableWidget(0, 11, self)
        self.assumptions.setObjectName('PDFColumnSteelAssumptions')
        self.assumptions.setHorizontalHeaderLabels([
            'تیپ','تعداد موقعیت','طول فرضی کل m','نام پروفیل (فرض)',
            'پروفیل/ستون (فرض)','kg/m (فرض)','ورق/ستون (فرض)',
            'طول ورق mm','عرض ورق mm','ضخامت ورق mm','چگالی kg/m³ (فرض)',
        ])
        self.assumptions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.assumptions.itemChanged.connect(self._assumptions_changed)
        layout.addWidget(self.assumptions)
        self.scenario_ack = QCheckBox('می‌پذیرم که ضرایب و ورق‌های واردشده فرض سناریویی هستند و از PDF تأیید نشده‌اند.')
        self.scenario_ack.setObjectName('PDFColumnScenarioAcknowledgment')
        self.scenario_ack.toggled.connect(self._scenario_changed)
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
        self.weight_receipt = QLabel()
        self.weight_receipt.setObjectName('PDFColumnWeightReceipt')
        self.weight_receipt.setTextFormat(Qt.TextFormat.PlainText)
        self.weight_receipt.setWordWrap(True)
        layout.addWidget(self.weight_receipt)
        self.export_receipt = QLabel()
        self.export_receipt.setObjectName('PDFColumnExportReceipt')
        self.export_receipt.setTextFormat(Qt.TextFormat.PlainText)
        self.export_receipt.setWordWrap(True)
        self.export_receipt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.export_receipt)
        self.weight_rows = QTableWidget(0, 5, self)
        self.weight_rows.setObjectName('PDFColumnWeightRows')
        self.weight_rows.setHorizontalHeaderLabels(['تیپ','تعداد','جرم پروفیل kg','جرم ورق kg','جرم کل سناریو kg'])
        self.weight_rows.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.weight_rows)
        path = next(iter(source_paths.values())) if source_paths and len(source_paths) == 1 else None
        self.set_source(path, expected_sha256=expected_sha256)

    def _pick_pdf(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'انتخاب فایل نقشه PDF', '', 'PDF (*.pdf)')
        if filename:
            self.set_source(filename)

    def set_source(self, pdf_path, *, expected_sha256=None):
        """Select a source and clear all draft results without starting extraction."""
        self.pdf_path = Path(pdf_path) if pdf_path else None
        self._expected_sha256 = expected_sha256
        self._reset()
        valid_suffix = self.pdf_path is not None and self.pdf_path.suffix.lower() == '.pdf'
        self.extract_button.setEnabled(valid_suffix)
        self.source_label.setText(f'PDF منبع: {self.pdf_path}' if self.pdf_path else 'PDF منبع انتخاب نشده است.')
        self.receipt.setText('برای خواندن نقشه، استخراج ستون‌ها را اجرا کنید.' if valid_suffix
                             else 'یک فایل با پسوند PDF انتخاب کنید.')

    def _reset(self):
        self.schedule = None
        self.positions.setRowCount(0)
        self.position_evidence.clear()
        with QSignalBlocker(self.assumptions), QSignalBlocker(self.scenario_ack):
            self.assumptions.setRowCount(0)
            self.scenario_ack.setChecked(False)
        self.scenario_ack.setEnabled(False)
        self.weight_button.setEnabled(False)
        self._clear_weight(self.NO_WEIGHT)

    def _clear_weight(self, message):
        self.weight_preview = None
        self.weight_rows.setRowCount(0)
        self.export_button.setEnabled(False)
        self.weight_receipt.setText(message)
        self.export_receipt.clear()

    def _scenario_changed(self):
        can_compute = bool(self.schedule and self.schedule.get('groups') and self.scenario_ack.isChecked())
        self.weight_button.setEnabled(can_compute)
        self._clear_weight('برای محاسبه با فرض‌های فعلی، محاسبه سناریو را بزنید.' if can_compute
                           else self.NO_WEIGHT)

    def _assumptions_changed(self, item):
        if item.column() >= 3 and self.weight_button.isEnabled():
            self.compute_weight()

    def _position_changed(self, index, *_):
        if not self.schedule or not 0 <= index < len(self.schedule['rows']):
            self.position_evidence.clear()
            return
        row = self.schedule['rows'][index]
        source_ids = '، '.join(row.get('source_operator_ids') or ()) or '—'
        self.position_evidence.setPlainText(
            f"شیت پلان: {row.get('plan_page') or '—'} | شیت دیتیل: {row.get('detail_page') or '—'}\n"
            f"نوشتهٔ اندازه در دیتیل: {row.get('printed_dimension_text') or '—'}\n"
            f"شناسه‌های عملگر شاهد در پلان: {source_ids}"
        )

    @staticmethod
    def _read_only(value):
        cell = QTableWidgetItem(str(value if value is not None else ''))
        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return cell

    def extract(self):
        self._reset()
        if not self.pdf_path or not self.pdf_path.is_file() or self.pdf_path.suffix.lower() != '.pdf':
            self.receipt.setText('استخراج ناموفق: یک فایل PDF موجود انتخاب کنید.')
            return
        try:
            if self._expected_sha256 is None:
                schedule = draft_column_length_schedule(self.pdf_path)
            else:
                schedule = draft_column_length_schedule(self.pdf_path, expected_sha256=self._expected_sha256)
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
        with QSignalBlocker(self.assumptions):
            self.assumptions.setRowCount(len(schedule.get('groups', ())))
            for i, group in enumerate(schedule.get('groups', ())):
                # Scenario defaults are demonstration inputs, not source readings.
                data = (group['type_tag'], group['grid_location_candidates'], group['draft_extended_length_m'],
                        'IPE16 (فرض)', '2', '15.8', '0', '', '', '', '7850')
                for j, value in enumerate(data):
                    cell = self._read_only(value) if j < 3 else QTableWidgetItem(str(value))
                    self.assumptions.setItem(i, j, cell)
        self.receipt.setText(
            f"{schedule['status']} | PDF SHA256: {schedule['document_sha256']} | "
            f"شیت پلان: {schedule.get('plan_page') or '—'} | تعداد شیت: {schedule.get('page_count') or '—'} | "
            f"{schedule.get('grid_node_count')} تقاطع | {schedule.get('draft_node_count')} تیپ خوانده‌شده | "
            f"طول سناریویی {schedule.get('draft_extended_length_total_m')} متر | "
            'بدون تأیید Revision، تعداد تکرار طبقات یا پرداخت مالی'
        )
        self.positions.setCurrentCell(0, 0)
        if schedule.get('groups'):
            self.scenario_ack.setEnabled(True)
            self.weight_receipt.setText('وزن محاسبه نشده است. فرض‌های هر تیپ را بازبینی و در صورت نیاز ویرایش کنید.')

    def _source_unchanged(self):
        if not self.pdf_path or not self.schedule:
            return False
        try:
            return sha256(self.pdf_path.read_bytes()).hexdigest() == self.schedule['document_sha256']
        except OSError:
            return False

    def _check_current_source(self):
        if self._source_unchanged():
            return True
        self._reset()
        message = 'فایل PDF پس از استخراج تغییر کرده یا در دسترس نیست؛ دوباره استخراج کنید.'
        self.receipt.setText(message)
        self.weight_receipt.setText(message)
        return False

    def compute_weight(self):
        if self.schedule is None or not self.schedule.get('groups'):
            return
        if not self._check_current_source():
            return
        if not self.scenario_ack.isChecked():
            self._clear_weight('ابتدا فرضی‌بودن ضرایب سناریو را تأیید کنید.')
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
            self._clear_weight('ورودی وزن نامعتبر: '+str(exc))
            return
        self.weight_preview=preview
        self.export_receipt.clear()
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
        self.export_button.setEnabled(True)

    def export(self):
        schedule, preview = self.schedule, self.weight_preview
        if schedule is None or preview is None or not self.scenario_ack.isChecked():
            return
        if not self._check_current_source():
            return
        name, selected = QFileDialog.getSaveFileName(
            self,'ذخیره متره آزمایشی ستون','column_type_weight_preview.xlsx',
            'Excel (*.xlsx);;CSV (*.csv);;JSON (*.json)')
        if not name:
            return
        if self.schedule is not schedule or self.weight_preview is not preview or not self._check_current_source():
            return
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix({'CSV (*.csv)': '.csv', 'JSON (*.json)': '.json'}.get(selected, '.xlsx'))
        if path.suffix.lower() not in ('.xlsx','.csv','.json'):
            QMessageBox.warning(self,'پسوند نامعتبر','فایل خروجی باید xlsx، csv یا json باشد.')
            return
        try:
            if path.suffix.lower()=='.xlsx':
                export_weight_preview_xlsx(schedule, preview, path)
            elif path.suffix.lower()=='.csv':
                write_weight_preview(preview, json_path=path.with_suffix('.json'), csv_path=path)
            else:
                path.write_text(json.dumps({'source_schedule':schedule,'weight_scenario':preview},
                                           ensure_ascii=False,indent=2),encoding='utf-8')
        except (OSError, ValueError, RuntimeError) as exc:
            self.export_receipt.setText('ذخیرهٔ خروجی ناموفق بود.')
            QMessageBox.warning(self,'خطای خروجی',str(exc))
            return
        saved = f'{path} | {path.with_suffix(".json")}' if path.suffix.lower() == '.csv' else str(path)
        self.export_receipt.setText(f'خروجی سناریوی غیرمالی ذخیره شد: {saved}')
