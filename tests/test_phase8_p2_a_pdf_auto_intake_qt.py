"""Synthetic Qt evidence-review checks, independent of financial approvals."""
import pytest

pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from app.pdf_auto_intake_review import PDFSheetEvidenceDialog


def test_pdf_intake_dialog_present_questions_no_auto_approval():
    app = QApplication.instance() or QApplication([])
    report = {'documents':[{'document_id':'PDF001'}], 'page_count':2,
              'member_type_candidates':[
                  {'tag':'C1','document_id':'PDF001','page':1,
                   'dimension_m':'10.70','status':'TYPE_DIMENSION_CANDIDATE'}],
              'unresolved_pages':[{'document_id':'PDF001','page':2,'reason':'No semantic text'}],
              'questions':[{'tag':'C1','question':'Which signed detail governs?',
                            'suggestion':{'status':'PROPOSED_UNVERIFIED','value':None}}]}
    dialog = PDFSheetEvidenceDialog(report)
    assert dialog.candidate_table.rowCount() == 1
    assert dialog.question_table.rowCount() == 1
    assert dialog.coverage_table.rowCount() == 1
    assert dialog.question_table.item(0,2).text().startswith('سند حاکم')
    assert 'تأیید مالی' in dialog.findChild(type(dialog.summary), 'PDFAutoIntakeNoFinanceWarning').text()
    dialog.close()