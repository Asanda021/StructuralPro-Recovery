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


def test_column_position_ledger_tab_preserves_unverified_floor_scope():
    app = QApplication.instance() or QApplication([])
    report = {
        'documents':[{'document_id':'PDF001','sha256':'a'*64}],
        'page_count':19,'member_type_candidates':[], 'grid_location_candidates':[],
        'unresolved_pages':[], 'questions':[],
        'column_position_ledger':{'positions':[{ 
            'candidate_id':'PDF001:p14:r1:c1',
            'axis_evidence':{'document_id':'PDF001','page':13},
            'proposed_type':'C2',
            'type_detail_evidence':{'page':19,'type_detail_length_m':'14.00'},
            'floor_instances_verified':None,'physical_member_quantity':None,
            'financially_payable':False,'status':'FOUR_WAY_DRAWING_EVIDENCE_CANDIDATE',
        }], 'floor_multiplier':None,'verified_total_physical_members':None},
    }
    dlg=PDFSheetEvidenceDialog(report)
    assert dlg.column_position_table.rowCount()==1
    assert dlg.column_position_table.item(0,1).text()=='آکس‌بندی صفحه 13'
    assert dlg.column_position_table.item(0,2).text()=='C2'
    assert '14.00' in dlg.column_position_table.item(0,3).text()
    assert 'نامعلوم' in dlg.column_position_table.item(0,4).text()
    assert 'غیرقطعی' in dlg.summary.text()
    assert dlg.ledger.answers=={}
    dlg.close()


def test_full_pdf_sheet_region_title_index_visible_without_amounts():
    app = QApplication.instance() or QApplication([])
    page = {'document_id':'PDF001','page':1,'sheet_kind':'beam_layout_plan',
            'region_count':2,'detail_anchor_count':2,'coverage_status':'UNRESOLVED'}
    region = {'region_id':'PDF001:p1:r1:c1',
              'bbox_pt':[0,0,150,125], 'text_block_count':1,
              'vector_path_count':17,'image_block_count':0,
              'status':'UNRESOLVED',
              'reason':'Vector content requires interpretation'}
    title = {'document_id':'PDF001','page':1,'title_preview':'Beam Detail B1',
             'bbox_pt':[10,12,80,25],'status':'UNRESOLVED'}
    report={'documents':[{'document_id':'PDF001','page_count':1,'sha256':'a'*64}],
            'page_count':1,'member_type_candidates':[],
            'grid_location_candidates':[],'unresolved_pages':[],'questions':[],
            'sheet_detail_inventory':{
              'sheet_inventory':[page], 'region_inventory':[region],
              'detail_title_anchors':[title],
              'all_input_pages_indexed':True,'complete':False,
              'quantity_approval_count':0}}
    dialog=PDFSheetEvidenceDialog(report)
    assert dialog.sheet_coverage_table.rowCount()==1
    assert dialog.sheet_coverage_table.item(0,1).text()=='beam_layout_plan'
    assert dialog.detail_region_table.rowCount()==1
    assert dialog.detail_region_table.item(0,5).text()=='UNRESOLVED'
    assert dialog.detail_region_table.item(0,5).toolTip().startswith('Vector')
    assert dialog.detail_title_table.rowCount()==1
    assert dialog.detail_title_table.item(0,1).text()=='Beam Detail B1'
    assert dialog.ledger.answers=={}
    dialog.close()


def test_multi_family_detail_object_and_orphan_zones_shown_with_no_boq_changes():
    app=QApplication.instance() or QApplication([])
    source={'documents':[{'document_id':'PDF001','page_count':1,'sha256':'a'*64}],
            'page_count':1,'member_type_candidates':[],
            'grid_location_candidates':[],'unresolved_pages':[],'questions':[],
            'detail_object_index':{
              'detail_candidates':[
                {'candidate_id':'DETAIL_TITLE:PDF001:p1:title1',
                 'document_id':'PDF001','page':1,
                 'title_preview':'Beam to Column Connection',
                 'type_tag':None,'family_candidates':['beam','column','reinforcement_connection'],
                 'region_ids':['PDF001:p1:r1:c1'],'kind':'EXPLICIT_DETAIL_TITLE',
                 'status':'MULTI_FAMILY_DETAIL_TITLE_CANDIDATE',
                 'financially_payable':False,'detail_boundary_verified':False},
                {'candidate_id':'TYPE_MARK:PDF001:p1:F2',
                 'document_id':'PDF001','page':1,'type_tag':'F2',
                 'family_candidates':['foundation'],'region_ids':['PDF001:p1:r2:c2'],
                 'kind':'EXPLICIT_TEXT_TYPE_MARK',
                 'status':'TYPE_MARK_WITH_VISUAL_EVIDENCE_CANDIDATE',
                 'financially_payable':False,'physical_member_verified':False}],
              'unassigned_visual_regions':[
                {'region_id':'PDF001:p1:r2:c1','document_id':'PDF001','page':1,
                 'vector_path_count':20,'image_block_count':0,
                 'reason':'Source vector drawing must be interpreted',
                 'status':'UNRESOLVED_UNLABELED_VISUAL_REGION',
                 'financially_payable':False}],
              'potential_same_document_type_references':[{
                'document_id':'PDF001','type_tag':'F2','pages':[1,3],
                'status':'POSSIBLE_SAME_DOCUMENT_TYPE_REFERENCE_UNVERIFIED'}],
              'semantic_details_fully_interpreted':False,
              'physical_member_count':None,'quantity_approval_count':0}
            }
    dialog=PDFSheetEvidenceDialog(source)
    assert dialog.detail_object_table.rowCount()==2
    assert 'beam' in dialog.detail_object_table.item(0,3).text()
    assert 'column' in dialog.detail_object_table.item(0,3).text()
    assert dialog.detail_object_table.item(1,2).text()=='F2'
    assert dialog.unassigned_visual_region_table.rowCount()==1
    assert 'UNRESOLVED' in dialog.unassigned_visual_region_table.item(0,3).text()
    assert dialog.type_reference_table.rowCount()==1
    assert dialog.type_reference_table.item(0,2).text()=='1, 3'
    assert dialog.ledger.answers=={}
    dialog.close()



def test_pdf_vector_proximity_groups_visible_as_nonfinancial_candidates():
    app=QApplication.instance() or QApplication([])
    report={'documents':[{'document_id':'PDF001'}],'page_count':1,
            'member_type_candidates':[],'unresolved_pages':[],'questions':[],
            'detail_object_index':{
                'vector_geometry_groups':[{
                    'candidate_id':'PDF001:p1:vector_group00001',
                    'bbox_pt':[20,30,100,130], 'source_path_count':2,
                    'nearby_title_anchor_ids':['PDF001:p1:title1'],
                    'status':'PROVISIONAL_BBOX_PROXIMITY_GROUP',
                    'reason':'Candidate only','financially_payable':False}],
                'vector_geometry_group_count':1,'vector_grouping_blocked_pages':[]}}
    dlg=PDFSheetEvidenceDialog(report)
    assert dlg.vector_group_table.rowCount()==1
    assert 'title1' in dlg.vector_group_table.item(0,3).text()
    assert 'نه دیتیل قطعی' in dlg.summary.text()
    assert dlg.ledger.answers=={}
    dlg.close()



def test_pdf_vector_grouping_blocked_page_is_visible_with_reason():
    app=QApplication.instance() or QApplication([])
    dlg=PDFSheetEvidenceDialog({
        'documents':[{'document_id':'PDF007'}],
        'page_count':1, 'member_type_candidates':[],
        'unresolved_pages':[], 'questions':[],
        'detail_object_index':{
            'vector_geometry_groups':[],
            'vector_geometry_group_count':0,
            'vector_grouping_blocked_pages':[{
                'document_id':'PDF007','page':3,
                'status':'BLOCKED_VECTOR_GROUP_PATH_BUDGET',
                'ungrouped_path_count':3001,
                'financially_payable':False,
            }]
        }
    })
    assert dlg.vector_group_blocked_table.rowCount()==1
    assert dlg.vector_group_blocked_table.item(0,0).text()=='PDF007:p3'
    assert dlg.vector_group_blocked_table.item(0,1).text()=='BLOCKED_VECTOR_GROUP_PATH_BUDGET'
    assert dlg.vector_group_blocked_table.item(0,2).text()=='3001'
    assert '1 صفحه هندسه گروه‌بندی‌نشده' in dlg.summary.text()
    assert dlg.ledger.answers=={}
    dlg.close()
