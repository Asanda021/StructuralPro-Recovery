"""Read-only review of automatic PDF-sheet evidence and necessary questions.

Intake never commits a member quantity, silently changes BOQ, or treats a
proposed answer as approved.  This view does not modify the source documents.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTabWidget, QWidget, QComboBox, QLineEdit,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from core.drawings.pdf_auto_questions import PDFQuestionDecisionLedger


class PDFSheetEvidenceDialog(QDialog):
    def __init__(self, report: dict, parent=None):
        super().__init__(parent)
        self.setObjectName('PDFSheetEvidenceReview')
        self.setWindowTitle('تحلیل خودکار شیت‌های PDF | شواهد و ابهام‌ها')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1000, 690)
        self.report = report
        self.ledger = PDFQuestionDecisionLedger(report)
        root = QVBoxLayout(self)
        self.summary = QLabel(
            f"{len(report.get('documents', ()))} PDF | {report.get('page_count', 0)} صفحه | "
            f"{len(report.get('member_type_candidates', ()))} شاهد تیپ | "
            f"{len(report.get('grid_location_candidates', ()))} نامزد موقعیت شبکه (تأییدنشده) | "
            f"{len(report.get('unresolved_pages', ()))} صفحه با پوشش نامعلوم | "
            f"{len(report.get('questions', ()))} ابهام بین شیت‌ها")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        disclaimer = QLabel(
            'این نتایج فقط شواهد هندسی/متنیِ شناسایی نوع عضو هستند. '
            'شمار اعضای فیزیکی، متره کامل و تأیید مالی هنوز احراز نشده‌اند.')
        disclaimer.setObjectName('PDFAutoIntakeNoFinanceWarning')
        disclaimer.setWordWrap(True)
        root.addWidget(disclaimer)
        tabs = QTabWidget(self)
        root.addWidget(tabs)
        candidates = QWidget(tabs)
        candidate_layout = QVBoxLayout(candidates)
        self.candidate_table = QTableWidget(0, 5, candidates)
        self.candidate_table.setObjectName('PDFAutoIntakeCandidates')
        self.candidate_table.setHorizontalHeaderLabels([
            'شناسه تیپ', 'سند / صفحه', 'بعد مستند', 'وضعیت', 'قابلیت استفاده مالی'])
        self.candidate_table.setRowCount(len(report.get('member_type_candidates', ())))
        self.candidate_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, row in enumerate(report.get('member_type_candidates', ())):
            vals = [row.get('tag', ''), f"{row.get('document_id','')}:p{row.get('page','')}",
                    f"{row.get('dimension_m') or 'نامشخص'} m" if row.get('dimension_m') else 'نامشخص',
                    row.get('status', ''), 'خیر']
            for j, text in enumerate(vals):
                cell = QTableWidgetItem(str(text))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.candidate_table.setItem(i, j, cell)
        candidate_layout.addWidget(self.candidate_table)
        tabs.addTab(candidates, 'شواهد تیپ‌ها')

        grid_tab = QWidget(tabs)
        grid_layout = QVBoxLayout(grid_tab)
        self.grid_table = QTableWidget(0, 5, grid_tab)
        self.grid_table.setObjectName('PDFAutoIntakeGridLocations')
        self.grid_table.setHorizontalHeaderLabels([
            'شناسه موقعیت', 'سند / صفحه', 'مختصات PDF (pt)',
            'تیپ پیشنهادی (غیرقطعی)', 'وضعیت',
        ])
        locations = report.get('grid_location_candidates', ())
        self.grid_table.setRowCount(len(locations))
        self.grid_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(locations):
            values = (
                item.get('candidate_id', ''),
                f"{item.get('document_id','')}:p{item.get('page','')}",
                f"({item.get('x_pt','')}, {item.get('y_pt','')})",
                item.get('suggested_type') or 'شناسایی نشده',
                item.get('status', ''),
            )
            for j, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid_table.setItem(i, j, cell)
        grid_layout.addWidget(self.grid_table)
        tabs.addTab(grid_tab, 'موقعیت‌های احتمالی شبکه')


        questions = QWidget(tabs)
        question_layout = QVBoxLayout(questions)
        self.question_table = QTableWidget(0, 3, questions)
        self.question_table.setObjectName('PDFAutoIntakeQuestions')
        self.question_table.setHorizontalHeaderLabels(['شناسه', 'سؤال ضروری برای کاربر نرم‌افزار', 'پیشنهاد مستند'])
        question_rows = report.get('questions', ())
        self.question_table.setRowCount(len(question_rows))
        self.question_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, question in enumerate(question_rows):
            suggestion = question.get('suggestion') or {}
            value = suggestion.get('value')
            guess = str(value) if value is not None else 'سند حاکم معلوم نیست؛ حدس قطعی مجاز نیست'
            for j, text in enumerate((question.get('tag',''), question.get('question',''), guess)):
                cell = QTableWidgetItem(str(text))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.question_table.setItem(i, j, cell)
        question_layout.addWidget(self.question_table)
        answer_row = QHBoxLayout()
        self.question_action = QComboBox()
        self.question_action.setObjectName('PDFAutoIntakeQuestionAction')
        self.question_action.addItem('درخواست سند اصلاحی', 'request_document')
        self.question_action.addItem('اصلاح پاسخ پیشنهادی', 'correct')
        self.question_action.addItem('تأیید پیشنهاد با ذکر مستند', 'confirm_suggestion')
        self.question_answer = QLineEdit()
        self.question_answer.setObjectName('PDFAutoIntakeQuestionCorrection')
        self.question_answer.setPlaceholderText('مقدار یا توضیح اصلاح‌شده در صورت انتخاب اصلاح')
        self.record_question = QPushButton('ثبت پاسخ بازبین (غیرمالی)')
        self.record_question.setObjectName('PDFAutoIntakeRecordQuestion')
        self.record_question.clicked.connect(self._record_question_answer)
        self.export_questions = QPushButton('ذخیره پاسخ‌های بازبینی')
        self.export_questions.setObjectName('PDFAutoIntakeExportAnswers')
        self.export_questions.clicked.connect(self._export_question_answers)
        for widget in (self.question_action, self.question_answer, self.record_question, self.export_questions):
            answer_row.addWidget(widget)
        question_layout.addLayout(answer_row)
        self.answer_status = QLabel('پاسخ‌ها فقط برای بازبینی ذخیره می‌شوند؛ مقدار مالی تغییر نمی‌کند.')
        self.answer_status.setWordWrap(True)
        question_layout.addWidget(self.answer_status)
        self.record_question.setEnabled(bool(question_rows))
        self.export_questions.setEnabled(bool(question_rows))
        tabs.addTab(questions, 'سؤال‌های ضروری')

        coverage = QWidget(tabs)
        coverage_layout = QVBoxLayout(coverage)
        self.coverage_table = QTableWidget(0, 2, coverage)
        self.coverage_table.setObjectName('PDFAutoIntakeUnresolvedPages')
        self.coverage_table.setHorizontalHeaderLabels(['سند / صفحه', 'محدودیت خوانش'])
        unknown = report.get('unresolved_pages', ())
        self.coverage_table.setRowCount(len(unknown))
        self.coverage_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(unknown):
            for j, text in enumerate((f"{item.get('document_id')}:p{item.get('page')}",
                                      item.get('reason', ''))):
                cell = QTableWidgetItem(str(text))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.coverage_table.setItem(i, j, cell)
        coverage_layout.addWidget(self.coverage_table)
        tabs.addTab(coverage, 'صفحات نیازمند شواهد بیشتر')

        row = QHBoxLayout()
        row.addWidget(QLabel('این پنجره فقط‌خواندنی است و مقدار پیشنهادی را به BOQ نمی‌فرستد.'))
        close = QPushButton('بستن گزارش')
        close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)

    def _record_question_answer(self):
        row = self.question_table.currentRow()
        if row < 0:
            selected = self.question_table.selectionModel().selectedRows()
            if selected:
                row = selected[0].row()
            elif self.question_table.rowCount() == 1:
                row = 0
        if row < 0 or row >= len(self.report.get('questions', ())):
            QMessageBox.information(self, 'پرسش مهندسی', 'برای ثبت پاسخ، یک سؤال را انتخاب کنید.')
            return
        tag = self.report['questions'][row]['tag']
        try:
            result = self.ledger.answer(
                tag, self.question_action.currentData(),
                value=self.question_answer.text(),
            )
            self.answer_status.setText(
                f"پاسخ {result['tag']} ثبت شد؛ صرفاً پیش‌نویس بازبینی، بدون تأیید مالی."
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, 'پاسخ نامعتبر', str(exc))

    def _export_question_answers(self):
        if not self.ledger.answers:
            QMessageBox.information(self, 'ذخیره پاسخ‌ها', 'هنوز هیچ پاسخی ثبت نشده است.')
            return
        name, _ = QFileDialog.getSaveFileName(self, 'ذخیره پرونده بازبینی PDF',
                                             'pdf_intake_review_draft.json', 'JSON (*.json)')
        if not name:
            return
        try:
            from pathlib import Path
            Path(name).write_text(self.ledger.export_json(), encoding='utf-8')
            self.answer_status.setText('پاسخ‌ها در پرونده بازبینی ذخیره شدند؛ BOQ تغییر نکرده است.')
        except OSError as exc:
            QMessageBox.warning(self, 'خطای ذخیره', str(exc))