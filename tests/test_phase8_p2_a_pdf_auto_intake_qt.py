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


def test_pdf_vector_symbol_witness_visible_without_promoting_to_member():
    app = QApplication.instance() or QApplication([])
    report = {
        'documents': [{'document_id': 'PDF001', 'sha256': 'b'*64}],
        'page_count': 1, 'member_type_candidates': [],
        'column_layout_symbol_candidate_count': 1,
        'unresolved_pages': [], 'questions': [],
        'grid_location_candidates': [{
            'candidate_id': 'PDF001:p1:r1:c1', 'document_id': 'PDF001', 'page': 1,
            'x_pt': 180, 'y_pt': 156, 'suggested_type': None,
            'symbol_status': 'COMPACT_VECTOR_SYMBOL_CANDIDATE',
            'column_context_candidate': True,
            'status': 'GRID_LOCATION_TYPE_UNKNOWN',
            'physical_member_verified': False, 'financially_payable': False,
        }],
    }
    dialog = PDFSheetEvidenceDialog(report)
    assert dialog.grid_table.rowCount() == 1
    assert dialog.grid_table.item(0, 5).text() == 'شاهد فشرده، غیرقطعی'
    assert dialog.grid_table.item(0, 3).text() == 'شناسایی نشده'
    assert 'غیرقطعی' in dialog.summary.text()
    assert dialog.ledger.answers == {}
    dialog.close()


def test_grouped_column_question_shows_known_types_without_auto_assignment():
    app = QApplication.instance() or QApplication([])
    report = {
        'documents':[{'document_id':'PDF001','sha256':'a'*64}],
        'page_count':1,'member_type_candidates':[],'grid_location_candidates':[],
        'unresolved_pages':[],
        'questions':[{'tag':'GRID_TYPE:PDF001:p1','status':'REVIEW_REQUIRED',
            'question':'تیپ علائم ستون‌ها چیست؟',
            'suggestion':{'status':'PROPOSED_UNVERIFIED','value':None,
                          'candidate_types_from_details':['C1','C2','C3']},
            'evidence':[{'document_id':'PDF001','page':1}]}],
    }
    dialog=PDFSheetEvidenceDialog(report)
    cell=dialog.question_table.item(0,2).text()
    assert 'C1' in cell and 'C2' in cell and 'C3' in cell
    assert 'نامعلوم' in cell
    assert dialog.ledger.answers=={}
    dialog.close()


def test_vector_type_and_detail_evidence_display_without_finance():
    app = QApplication.instance() or QApplication([])
    report = {
        'documents': [{'document_id':'PDF001','sha256':'a'*64}],
        'page_count':2,'member_type_candidates':[],
        'column_layout_symbol_candidate_count':1,
        'vector_type_label_candidate_count':1,'vector_type_detail_link_count':1,
        'unresolved_pages':[],
        'grid_location_candidates':[{
            'candidate_id':'PDF001:p1:r1:c1','document_id':'PDF001','page':1,
            'x_pt':180,'y_pt':150,'suggested_type':'C2',
            'status':'GRID_LOCATION_VECTOR_TYPE_CANDIDATE',
            'symbol_status':'COMPACT_VECTOR_SYMBOL_CANDIDATE',
            'vector_type_label_evidence':{'tag':'C2','status':'PROPOSED_UNVERIFIED'},
            'cross_sheet_type_reference':{'tag':'C2','status':'PROPOSED_UNVERIFIED',
                'details':[{'page':2,'dimension_kind':'length','dimension_m':'12.50'}]},
            'type_verified':False,'physical_member_verified':False,
            'financially_payable':False,
        }],
        'questions':[{'tag':'GRID_TYPE:PDF001:p1',
          'question':'آیا انتساب تیپ‌ها معتبر است؟',
          'suggestion':{'value':None,'status':'PROPOSED_UNVERIFIED',
            'per_location_type_candidates':[{'candidate_id':'PDF001:p1:r1:c1',
              'type':'C2','status':'PROPOSED_UNVERIFIED'}]},
          'evidence':[{'document_id':'PDF001','page':1}]}],
    }
    dlg=PDFSheetEvidenceDialog(report)
    assert dlg.grid_table.item(0,3).text()=='C2'
    assert 'تأیید مهندسی نشده' in dlg.grid_table.item(0,3).toolTip()
    assert '12.50 m' in dlg.grid_table.item(0,3).toolTip()
    assert 'C2: 1' in dlg.question_table.item(0,2).text()
    assert 'غیرمالی' in dlg.question_table.item(0,2).text()
    assert 'ارتباط پیشنهادی با دیتیل' in dlg.summary.text()
    assert dlg.ledger.answers=={}
    dlg.close()



def test_axis_witness_and_floor_scope_are_review_only():
    app=QApplication.instance() or QApplication([])
    floor=[{'document_id':'PDF001','page':2,'sheet_kind':'ground_floor_plan'}]
    report={'documents':[{'document_id':'PDF001','sha256':'a'*64}],
       'page_count':2,'member_type_candidates':[],
       'independently_registered_grid_positions':1,
       'architectural_floor_plan_candidates':floor,
       'unresolved_pages':[],
       'grid_location_candidates':[{
           'candidate_id':'PDF001:p2:r1:c1',
           'document_id':'PDF001','page':2,'x_pt':180,'y_pt':156,
           'suggested_type':'C1','status':'GRID_LOCATION_VECTOR_TYPE_CANDIDATE',
           'independent_axis_grid_witness':{
               'axis_document_id':'PDF001','axis_page':1,
               'axis_candidate_id':'PDF001:p1:r1:c1',
               'max_residual_pt':0.0,
               'status':'PROPOSED_INDEPENDENT_GRID_REGISTRATION',
               'physical_member_verified':False,'financially_payable':False,
           },
           'type_verified':False,'financially_payable':False,
       }],
       'questions':[{'tag':'COLUMN_FLOOR_SCOPE',
           'question':'ستون‌ها در کدام طبقات اجرا شده‌اند؟',
           'suggestion':{'value':None,'status':'PROPOSED_UNVERIFIED',
                         'floor_plan_candidates':floor},
           'evidence':[{'document_id':'PDF001','page':2}]}]}
    dialog=PDFSheetEvidenceDialog(report)
    assert dialog.floor_table.rowCount()==1
    assert 'نامعلوم' in dialog.floor_table.item(0,2).text()
    assert 'آکس‌بندی صفحه 1' in dialog.grid_table.item(0,4).toolTip()
    assert 'بدون ضریب تکرار' in dialog.summary.text()
    assert 'تعداد تکرار' in dialog.question_table.item(0,2).text()
    assert dialog.ledger.answers=={}
    dialog.close()
