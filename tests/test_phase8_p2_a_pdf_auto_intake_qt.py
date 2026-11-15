"""Synthetic Qt evidence-review checks, independent of financial approvals."""
import pytest

pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from app.pdf_auto_intake_review import PDFSheetEvidenceDialog


def test_pdf_intake_dialog_present_questions_no_auto_approval():
    app = QApplication.instance() or QApplication([])
    report = {'documents':[{'document_id':'PDF001', 'sha256':'a'*64}], 'page_count':2,
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
    assert dialog.record_question.isEnabled()
    assert dialog.ledger.answers == {}
    dialog.question_table.selectRow(0)
    dialog._record_question_answer()
    assert dialog.ledger.answers['C1']['decision'] == 'request_document'
    assert dialog.ledger.answers['C1']['financially_payable'] is False
    assert dialog.question_table.item(0,2).text().startswith('سند حاکم')
    assert 'تأیید مالی' in dialog.findChild(type(dialog.summary), 'PDFAutoIntakeNoFinanceWarning').text()
    dialog.close()

def test_pdf_grid_location_candidates_are_visible_but_not_members_or_boq():
    app = QApplication.instance() or QApplication([])
    report = {
        'documents': [{'document_id': 'PDF001', 'sha256': 'b'*64}],
        'page_count': 1, 'member_type_candidates': [],
        'unresolved_pages': [], 'questions': [],
        'grid_location_candidates': [{
            'candidate_id': 'PDF001:p1:r1:c1', 'document_id': 'PDF001', 'page': 1,
            'x_pt': 180, 'y_pt': 156, 'suggested_type': None,
            'status': 'GRID_LOCATION_TYPE_UNKNOWN', 'financially_payable': False,
        }],
    }
    dialog = PDFSheetEvidenceDialog(report)
    assert dialog.grid_table.rowCount() == 1
    assert dialog.grid_table.item(0, 3).text() == 'شناسایی نشده'
    assert 'تأییدنشده' in dialog.summary.text()
    assert not dialog.record_question.isEnabled()
    assert dialog.ledger.answers == {}
    dialog.close()
