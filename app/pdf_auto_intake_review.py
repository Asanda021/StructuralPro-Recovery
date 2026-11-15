"""Read-only review of automatic PDF-sheet evidence and necessary questions.

Intake never commits a member quantity, silently changes BOQ, or treats a
proposed answer as approved.  This view does not modify the source documents.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTabWidget, QWidget,
)
from PySide6.QtCore import Qt


class PDFSheetEvidenceDialog(QDialog):
    def __init__(self, report: dict, parent=None):
        super().__init__(parent)
        self.setObjectName('PDFSheetEvidenceReview')
        self.setWindowTitle('تحلیل خودکار شیت‌های PDF | شواهد و ابهام‌ها')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1000, 690)
        self.report = report
        root = QVBoxLayout(self)
        self.summary = QLabel(
            f"{len(report.get('documents', ()))} PDF | {report.get('page_count', 0)} صفحه | "
            f"{len(report.get('member_type_candidates', ()))} شاهد تیپ | "
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