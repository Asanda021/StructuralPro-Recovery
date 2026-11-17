"""Synthetic Qt tests of engineering decisions and their source evidence."""
from copy import deepcopy

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton

from app.pdf_auto_intake_review import PDFSheetEvidenceDialog


@pytest.fixture(scope='module')
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def engineering_report():
    plan = {'anchor_id': 'plan-mark', 'document_id': 'PDF001', 'page': 1,
            'bbox_pt': [11, 15, 35, 41], 'kind': 'COLUMN_PLAN_GLYPH',
            'source_name': 'synthetic-plan.pdf', 'source_sha256': 'a' * 64,
            'raw_token': 'C-07 C2'}
    schedule = {'anchor_id': 'detail-mark', 'document_id': 'PDF002', 'page': 2,
                'bbox_pt': [60, 70, 80, 90], 'kind': 'NATIVE_TYPE_DETAIL_DIMENSION',
                'source_name': 'synthetic-detail.pdf', 'source_sha256': 'b' * 64,
                'printed': 'C2 | 3 Nos. | L=14.00 m', 'dimension_m': '14.00'}
    axes = {'anchor_id': 'axis-mark', 'document_id': 'PDF003', 'page': 1,
            'bbox_pt': [90, 80, 120, 100], 'kind': 'AXIS',
            'source_name': 'synthetic-axes.pdf', 'source_sha256': 'c' * 64, 'raw_token': 'A/3'}
    page = {**plan, 'anchor_id': 'plan-page', 'bbox_pt': [0, 0, 600, 500], 'kind': 'SHEET_EXTENT',
            'raw_token': 'BEAM FRAMING PLAN | L1'}
    beam = {'anchor_id': 'beam-mark', 'document_id': 'PDF001', 'page': 1,
            'bbox_pt': [70, 80, 85, 95], 'kind': 'NATIVE_TYPE_WORD',
            'source_ref': 'PDF001:p1:word000001', 'source_token': 'B-1'}
    return {
        'documents': [
            {'document_id': 'PDF001', 'source_name': 'synthetic-plan.pdf', 'sha256': 'a' * 64, 'page_count': 1,
             'metadata': {'title': 'Synthetic Structural Layout Set'}},
            {'document_id': 'PDF002', 'source_name': 'synthetic-detail.pdf', 'sha256': 'b' * 64, 'page_count': 2},
            {'document_id': 'PDF003', 'source_name': 'synthetic-axes.pdf', 'sha256': 'c' * 64, 'page_count': 1},
        ],
        'page_count': 4,
        'questions': [],
        'detail_evidence_graph': {
            'graph_sha256': 'd' * 64,
            'quantity_approval_count': 0,
            'nodes': [
                {'node_id': 'occurrence', 'kind': 'INSTANCE_CANDIDATE', 'label': 'Plan mark C-07',
                 'status': 'UNRESOLVED', 'level': 'L1', 'anchors': [plan]},
                {'node_id': 'detail', 'kind': 'TYPE_DEFINITION', 'label': 'Printed C2 schedule',
                 'status': 'EXAMINED', 'anchors': [schedule]},
                {'node_id': 'axis', 'kind': 'AXIS', 'label': 'Axis A/3', 'status': 'EXAMINED', 'anchors': [axes]},
                {'node_id': 'sheet', 'kind': 'SHEET', 'label': 'Structural sheet', 'status': 'EXAMINED', 'anchors': [page]},
            ],
            'edges': [
                {'edge_id': 'detail-link', 'relationship': 'COLUMN_PLAN_TYPE_DETAIL',
                 'source_id': 'occurrence', 'target_id': 'detail', 'status': 'BLOCKED',
                 'reason': 'Conflicting printed count', 'anchors': [plan, schedule]},
                {'edge_id': 'axis-link', 'relationship': 'AT_AXIS', 'source_id': 'occurrence', 'target_id': 'axis',
                 'status': 'VALIDATED_REFERENCE', 'reason': 'Independent printed grid', 'anchors': [axes]},
            ],
            'occurrence_reviews': [{
                'node_id': 'occurrence', 'source_id': 'occurrence', 'target_id': 'detail', 'axis_node_ids': ['axis'],
                'printed_member_id': 'C-07', 'type_tag': 'C2', 'family': 'column', 'status': 'BLOCKED',
                'decision_code': 'DESIGN_AUTHORITY_REQUIRED', 'reason_code': 'C2_PRINTED_SCHEDULE_CONFLICT',
                'level': 'L1', 'axis': 'A/3', 'governing_revision': 'R2',
                'observations': {'plan_mark_count': 4, 'printed_schedule_count': 3},
                'missing_evidence': ['DESIGN_AUTHORITY_DECISION', 'SECTION_DIMENSIONS'],
                'anchors': [plan], 'conflicting_anchors': [schedule], 'quantity_status': 'BLOCKED',
                'quantity_unit': None, 'quantity_formula': None, 'member_quantity': None, 'financially_payable': False,
            }],
            'structural_plan_reviews': [{
                'node_id': 'sheet', 'source_id': 'sheet', 'target_id': None, 'role': 'BEAM_FRAMING_PLAN',
                'family': 'beam', 'status': 'REVIEW_REQUIRED', 'type_tag': 'B1',
                'reason_code': 'STRUCTURAL_PLAN_DETAIL_UNRESOLVED', 'reason': 'Explicit beam detail is missing',
                'missing_evidence': ['OCCURRENCE_DETAIL', 'LOCAL_SCALE_CALIBRATION'],
                'anchors': [page, beam],
            }],
        },
    }


def _select(review, key):
    review.sections.setCurrentIndex(review._section_keys.index(key))
    table = review.tables[key]
    index = table.model().index(0, 0)
    assert index.isValid()
    table.setCurrentIndex(index)
    return index


def test_occurrence_review_keeps_conflict_authority_and_drawing_sources(qt_app, engineering_report):
    before = deepcopy(engineering_report)
    dialog = PDFSheetEvidenceDialog(engineering_report)
    review = dialog.graph_review
    try:
        index = _select(review, 'occurrence_reviews')
        assert review.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert not index.flags() & Qt.ItemFlag.ItemIsEditable
        assert review.details.isReadOnly()
        selected = review.details.toPlainText()
        for value in (
            'C-07', 'C2_PRINTED_SCHEDULE_CONFLICT', 'DESIGN_AUTHORITY_REQUIRED', 'BLOCKED',
            'DESIGN_AUTHORITY_DECISION', 'SECTION_DIMENSIONS', 'L1', 'A/3', 'R2',
            'plan_mark_count', 'printed_schedule_count', 'مقدار عضو — —', 'قابل پرداخت مالی — خیر',
            'C-07 C2', 'C2 | 3 Nos. | L=14.00 m', '14.00',
            'synthetic-plan.pdf (PDF001) | صفحه 1 | کادر (pt) [11, 15, 35, 41]',
            'synthetic-detail.pdf (PDF002) | صفحه 2 | کادر (pt) [60, 70, 80, 90]',
            'a' * 64, 'b' * 64, 'شواهد ناسازگار',
        ):
            assert value in selected

        review.filters['nodes'].setText('Plan mark')
        review.findChild(QPushButton, 'PDFDetailGraphNavigateTarget').click()
        assert review.sections.currentIndex() == 2
        assert 'Printed C2 schedule' in review.details.toPlainText()

        review.sections.setCurrentIndex(review._section_keys.index('occurrence_reviews'))
        links = review.findChild(QToolButton, 'PDFDetailGraphRelatedEvidence').menu()
        axis = next(action for action in links.actions() if 'Axis A/3' in action.text())
        axis.trigger()
        assert review.sections.currentIndex() == 2
        assert 'synthetic-axes.pdf' in review.details.toPlainText()

        review.sections.setCurrentIndex(review._section_keys.index('occurrence_reviews'))
        detail_link = next(action for action in links.actions() if 'COLUMN_PLAN_TYPE_DETAIL' in action.text())
        review.filters['edges'].setText('AT_AXIS')
        detail_link.trigger()
        assert review.sections.currentIndex() == 3
        assert 'Conflicting printed count' in review.details.toPlainText()
        assert engineering_report == before
        assert dialog.ledger.answers == {}
    finally:
        dialog.close()


def test_structural_review_opens_plan_sheet_with_no_invented_detail(qt_app, engineering_report):
    dialog = PDFSheetEvidenceDialog(engineering_report)
    review = dialog.graph_review
    try:
        assert review._section_keys[:7] == [
            'documents', 'pages', 'nodes', 'edges', 'topology', 'issues', 'member_review_groups',
        ]
        _select(review, 'structural_plan_reviews')
        selected = review.details.toPlainText()
        for value in (
            'BEAM_FRAMING_PLAN', 'beam', 'B1', 'REVIEW_REQUIRED', 'STRUCTURAL_PLAN_DETAIL_UNRESOLVED',
            'Explicit beam detail is missing', 'OCCURRENCE_DETAIL', 'LOCAL_SCALE_CALIBRATION',
            'BEAM FRAMING PLAN | L1', 'synthetic-plan.pdf (PDF001) | صفحه 1 | کادر (pt) [0, 0, 600, 500]',
            'B-1', 'PDF001:p1:word000001', 'عنوان PDF — Synthetic Structural Layout Set',
        ):
            assert value in selected
        assert not review.findChild(QPushButton, 'PDFDetailGraphNavigateTarget').isEnabled()
        review.findChild(QPushButton, 'PDFDetailGraphNavigateSource').click()
        assert review.sections.currentIndex() == 2
        assert 'Structural sheet' in review.details.toPlainText()
        assert engineering_report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_occurrence_preview_displays_dimension_scope_and_nonfinancial_quantity(qt_app, engineering_report):
    graph = engineering_report['detail_evidence_graph']
    row, = graph['occurrence_reviews']
    row.update(status='COMPLETE_NONFINANCIAL', decision_code='COMPLETE_DRAWING_EVIDENCE', reason_code=None,
               missing_evidence=[], conflicting_anchors=[], quantity_status='TEMPORARY_NONFINANCIAL',
               member_quantity='0.56', quantity_unit='m3', quantity_formula='0.40 × 0.50 × 3.00 − 0.04',
               observations={'section_width_m': '0.4', 'section_depth_m': '0.5', 'length_m': '3',
                             'installation_from_m': '1.2', 'installation_to_m': '4.2', 'deductions_m3': '0.04'})
    row['anchors'].append({
        **graph['nodes'][1]['anchors'][0], 'anchor_id': 'section-width',
        'printed': 'COLUMN DIM C-07 TYPE C2 WIDTH 400 MM', 'dimension_m': '0.40', 'dimension_kind': 'WIDTH',
    })
    dialog = PDFSheetEvidenceDialog(engineering_report)
    try:
        _select(dialog.graph_review, 'occurrence_reviews')
        selected = dialog.graph_review.details.toPlainText()
        for value in ('COMPLETE_NONFINANCIAL', 'TEMPORARY_NONFINANCIAL', 'مقدار عضو — 0.56',
                      'واحد متره — m3', '0.40 × 0.50 × 3.00 − 0.04',
                      'عرض مقطع (m) — 0.4', 'عمق مقطع (m) — 0.5', 'طول اجرایی (m) — 3',
                      'تراز ابتدای نصب (m) — 1.2', 'تراز انتهای نصب (m) — 4.2',
                      'WIDTH 400 MM', 'نوع بُعد — WIDTH', 'بُعد چاپی (m) — 0.40', 'قابل پرداخت مالی — خیر'):
            assert value in selected
        assert graph['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_foundation_discrepancy_shows_per_sheet_printed_mark_counts(qt_app, engineering_report):
    row, = engineering_report['detail_evidence_graph']['structural_plan_reviews']
    row.update(role='FOUNDATION_MARK_COUNT_DISCREPANCY', family='foundation', status='BLOCKED', type_tag='F4',
               reason_code='FOUNDATION_PHASE_MARK_COUNT_MISMATCH', sheet_mark_counts=[
                   {'document_id': 'PDF002', 'source_name': 'synthetic-detail.pdf', 'page': 1,
                    'sheet_kind': 'excavation_plan', 'count': 1},
                   {'document_id': 'PDF002', 'source_name': 'synthetic-detail.pdf', 'page': 2,
                    'sheet_kind': 'foundation_plan', 'count': 2},
               ])
    dialog = PDFSheetEvidenceDialog(engineering_report)
    try:
        _select(dialog.graph_review, 'structural_plan_reviews')
        selected = dialog.graph_review.details.toPlainText()
        assert 'فراوانی نشانه‌های چاپی' in selected
        assert 'synthetic-detail.pdf (PDF002) | صفحه 1 | پلان پی‌کنی — 1' in selected
        assert 'synthetic-detail.pdf (PDF002) | صفحه 2 | پلان فونداسیون — 2' in selected
    finally:
        dialog.close()


def test_private_beam_profile_receipt_displays_nonpayable_spatial_review(qt_app, engineering_report, monkeypatch):
    calls = []
    graph = engineering_report['detail_evidence_graph']
    anchor = {'anchor_id': 'visual-beam15', 'document_id': 'PDF001', 'page': 1,
              'source_name': 'synthetic-plan.pdf', 'source_sha256': 'a'*64,
              'bbox_pt': [200, 155, 252, 195], 'kind': 'VISUALLY_READ_BEAM_PROFILE',
              'raw_token': '2IPE16', 'source_ref': 'test-visual-profile'}
    graph['beam_profile_reviews'] = [{
        'review_id': 'visual-review-1', 'role': 'BEAM_PROFILE_SPATIAL_REVIEW',
        'family': 'beam', 'profile_text': '2IPE16', 'type_tag': None,
        'printed_axis_row': '3', 'span_axes': 'A-B', 'circled_mark_raw': '1',
        'candidate_region_count': 1, 'candidate_review_ids': ['L1'],
        'status': 'REVIEW_REQUIRED', 'reason_code': 'BEAM_PROFILE_PROXIMITY_ONLY',
        'financially_payable': False, 'member_quantity': None,
        'missing_evidence': ['آکس، تکیه‌گاه و تراز نصب'],
        'anchors': [anchor],
    }]
    dialog = PDFSheetEvidenceDialog(engineering_report,
                                   attach_beam_profile_witnesses=lambda path: calls.append(path))
    review = dialog.graph_review
    try:
        _select(review, 'beam_profile_reviews')
        text = review.details.toPlainText()
        for token in ('2IPE16', 'A-B', 'REVIEW_REQUIRED', 'BEAM_PROFILE_PROXIMITY_ONLY',
                      'آکس، تکیه‌گاه و تراز نصب', 'قابل پرداخت مالی — خیر', 'synthetic-plan.pdf'):
            assert token in text
        button = review.findChild(QPushButton, 'PDFDetailAttachBeamProfileWitnesses')
        assert button is not None
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *args, **kwargs: ('/private/beam-witness.json', 'JSON (*.json)'))
        button.click()
        assert calls == ['/private/beam-witness.json']
        assert graph['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_rejected_beam_profile_receipt_leaves_previous_report_visible(qt_app, engineering_report, monkeypatch):
    def reject(_path):
        raise ValueError('SHA mismatch')
    dialog = PDFSheetEvidenceDialog(engineering_report, attach_beam_profile_witnesses=reject)
    review = dialog.graph_review
    try:
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *args, **kwargs: ('/private/foreign.json', 'JSON (*.json)'))
        review.findChild(QPushButton, 'PDFDetailAttachBeamProfileWitnesses').click()
        assert 'SHA mismatch' in review.beam_profile_status.text()
        assert review.tables['occurrence_reviews'].model().rowCount() == 1
        assert engineering_report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_independent_axis_tab_and_import_keep_original_receipt_readonly(qt_app, engineering_report, monkeypatch):
    original = deepcopy(engineering_report)
    graph = engineering_report['detail_evidence_graph']
    graph['beam_axis_grid_candidates'] = [{
        'document_id': 'PDF001', 'page': 13, 'source_name': 'synthetic-plan.pdf',
        'source_sha256': 'a'*64, 'status': 'PROPOSED_UNLABELED_AXIS_GRID',
        'grid_x_pt': [10, 45, 80, 115, 150],
        'grid_y_pt': [12, 60, 108],
        'axis_label_witness_status': 'NOT_INFERRED_FROM_LINES',
        'source_operator_refs': ['p13:d1:s1'],
        'printed_unit': None, 'financially_payable': False,
    }]
    original = deepcopy(engineering_report)
    choices = []
    dialog = PDFSheetEvidenceDialog(
        engineering_report,
        attach_beam_axis_labels=lambda path: choices.append(path),
    )
    try:
        review = dialog.graph_review
        _select(review, 'beam_axis_grid_candidates')
        visible = review.details.toPlainText()
        for label in ('PROPOSED_UNLABELED_AXIS_GRID', 'NOT_INFERRED_FROM_LINES',
                      'synthetic-plan.pdf', 'قابل پرداخت مالی — خیر', 'p13:d1:s1'):
            assert label in visible
        button = review.findChild(QPushButton, 'PDFDetailAttachIndependentBeamAxis')
        assert button is not None
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *a, **kw: ('/private/axes.json', 'JSON (*.json)'))
        button.click()
        assert choices == ['/private/axes.json']
        assert engineering_report == original
        assert graph['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_bad_independent_axis_receipt_stays_fail_closed(qt_app, engineering_report, monkeypatch):
    def bad_input(_):
        raise ValueError('source hash mismatch')
    dialog = PDFSheetEvidenceDialog(engineering_report, attach_beam_axis_labels=bad_input)
    try:
        review = dialog.graph_review
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *a, **kw: ('/private/wrong.json', 'JSON (*.json)'))
        review.findChild(QPushButton, 'PDFDetailAttachIndependentBeamAxis').click()
        assert 'source hash mismatch' in review.beam_axis_status.text()
        assert review.tables['occurrence_reviews'].model().rowCount() == 1
        assert engineering_report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_beam_two_end_symbols_and_type_only_detail_are_readonly(qt_app, engineering_report, monkeypatch):
    graph = engineering_report['detail_evidence_graph']
    image = {'anchor_id': 'p15-square-1', 'document_id': 'PDF001', 'page': 1,
             'source_name': 'synthetic-plan.pdf', 'source_sha256': 'a'*64,
             'kind': 'FILLED_GRID_END_MARKER_CANDIDATE', 'bbox_pt': [35, 50, 41, 56],
             'source_operator_refs': ['p1:d1','p1:d2']}
    graph['beam_end_marker_pages'] = [{
        'document_id': 'PDF001', 'page': 1, 'source_sha256': 'a'*64,
        'status': 'PROPOSED_UNVERIFIED_SQUARE_MARKERS', 'marker_count': 15,
        'duplicate_source_strokes': 17, 'financially_payable': False,
    }]
    graph['beam_end_support_reviews'] = [{
        'review_id': 'beam-two-end-1', 'node_id': 'beam-node', 'source_id': 'sheet',
        'span_axes': 'A-B', 'printed_axis_row': '3', 'profile_text': '2IPE16',
        'status': 'PROPOSED_BOTH_END_GRID_SYMBOLS',
        'detail_status': 'PROPOSED_TYPE_ONLY_NOT_SPAN_SPECIFIC',
        'candidate_detail_count': 1, 'endpoint_marker_ids': ['square-1', 'square-2'],
        'axis_page': 13, 'detail_page': 17,
        'missing_evidence': ['EXPLICIT_DETAIL_CALLOUT_FOR_THIS_SPAN', 'CUT_LENGTH'],
        'support_verified': False, 'detail_link_verified': False,
        'member_quantity': None, 'financially_payable': False,
        'anchors': [image], 'edge_ids': [],
    }]
    import_calls = []
    original = deepcopy(engineering_report)
    dialog = PDFSheetEvidenceDialog(engineering_report,
                   attach_beam_detail_profile_witnesses=lambda path: import_calls.append(path))
    review = dialog.graph_review
    try:
        _select(review, 'beam_end_marker_pages')
        assert '15' in review.details.toPlainText()
        _select(review, 'beam_end_support_reviews')
        selected = review.details.toPlainText()
        for token in ('A-B', '2IPE16', 'PROPOSED_BOTH_END_GRID_SYMBOLS',
                      'PROPOSED_TYPE_ONLY_NOT_SPAN_SPECIFIC', 'CUT_LENGTH',
                      'قابل پرداخت مالی — خیر', 'synthetic-plan.pdf'):
            assert token in selected
        button = review.findChild(QPushButton, 'PDFDetailAttachBeamConnectionDetails')
        assert button is not None
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *args, **kwargs: ('/private/p17-typed.json', 'JSON (*.json)'))
        button.click()
        assert import_calls == ['/private/p17-typed.json']
        assert engineering_report == original
    finally:
        dialog.close()


def test_rejected_connection_detail_never_mutates_current_qt_receipt(qt_app, engineering_report, monkeypatch):
    def reject(_path):
        raise ValueError('foreign PDF sha256')
    dialog = PDFSheetEvidenceDialog(engineering_report,
                                   attach_beam_detail_profile_witnesses=reject)
    try:
        review = dialog.graph_review
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *args, **kwargs: ('/private/foreign17.json', 'JSON (*.json)'))
        review.findChild(QPushButton, 'PDFDetailAttachBeamConnectionDetails').click()
        assert 'foreign PDF sha256' in review.beam_detail_status.text()
        assert review.tables['occurrence_reviews'].model().rowCount() == 1
        assert engineering_report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_beam_document_requests_are_nonfinancial_and_readable(qt_app, engineering_report):
    graph = engineering_report['detail_evidence_graph']
    anchor = {'anchor_id': 'beam-visual:1', 'document_id': 'PDF001', 'page': 1,
              'source_name': 'synthetic-plan.pdf', 'source_sha256': 'a'*64,
              'kind': 'VISUALLY_READ_BEAM_PROFILE', 'bbox_pt': [70, 80, 85, 95]}
    graph['beam_span_evidence_requests'] = [{
        'request_id': 'BEAM_MISSING_DOCUMENT:test', 'span_axes': 'A-B',
        'printed_axis_row': '3', 'printed_mark': '1', 'profile_visual': '2IPE16',
        'status': 'BLOCKED_REQUIRES_GOVERNING_ENGINEERING_DOCUMENTS',
        'beam_page': 1, 'axis_page': 2, 'detail_page': 3,
        'type_only_detail_matches': 1,
        'required_evidence_codes': ['SPAN_SPECIFIC_CONNECTION_DETAIL', 'FABRICATION_CUT_LENGTH'],
        'missing_evidence': ['SPAN_SPECIFIC_CONNECTION_DETAIL', 'FABRICATION_CUT_LENGTH'],
        'physical_member_verified': False, 'member_quantity': None,
        'financially_payable': False, 'anchors': [anchor],
    }]
    original = deepcopy(engineering_report)
    dialog = PDFSheetEvidenceDialog(engineering_report)
    try:
        review = dialog.graph_review
        _select(review, 'beam_span_evidence_requests')
        visible = review.details.toPlainText()
        for token in ('A-B', '2IPE16', 'BLOCKED_REQUIRES_GOVERNING_ENGINEERING_DOCUMENTS',
                      'SPAN_SPECIFIC_CONNECTION_DETAIL', 'FABRICATION_CUT_LENGTH',
                      'ارجاع اختصاصی دهانه', 'قابل پرداخت مالی — خیر', 'synthetic-plan.pdf'):
            assert token in visible
        assert engineering_report == original
        assert graph['quantity_approval_count'] == 0
    finally:
        dialog.close()



def _synthetic_beam_rfi_report(engineering_report):
    report = deepcopy(engineering_report)
    report['documents'] = report['documents'][:1]
    graph = report['detail_evidence_graph']
    graph['beam_span_request_status'] = 'BLOCKED_AWAITING_GOVERNING_ENGINEERING_DOCUMENTS'
    graph['beam_span_evidence_requests'] = [{
        'request_id': 'BEAM_MISSING_DOCUMENT:'+'c'*32,
        'source_sha256': 'a'*64, 'beam_page': 15, 'detail_page': 17,
        'span_axes': 'A-B', 'printed_axis_row': '1', 'printed_mark': '5',
        'profile_visual': '2IPE18', 'end_review_id': 'END-RFI-1',
        'required_evidence_codes': ['GOVERNING_DRAWING_ISSUE','FABRICATION_CUT_LENGTH'],
        'status': 'BLOCKED_REQUIRES_GOVERNING_ENGINEERING_DOCUMENTS',
        'financially_payable': False, 'physical_member_verified': False,
        'quantity_approved': False, 'member_quantity': None,
    }]
    return report


def test_designer_rfi_export_is_private_and_not_sent(qt_app, engineering_report, tmp_path, monkeypatch):
    import json
    report = _synthetic_beam_rfi_report(engineering_report)
    unchanged = deepcopy(report)
    dialog = PDFSheetEvidenceDialog(report)
    try:
        review = dialog.graph_review
        button = review.findChild(QPushButton, 'PDFDetailExportDesignerRFI')
        assert button is not None and button.isEnabled()
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getExistingDirectory',
                            lambda *args, **kwargs: str(tmp_path))
        button.click()
        children = list(tmp_path.glob('StructuralPro_RFI_*'))
        assert len(children) == 1
        packet=json.loads((children[0]/'PRIVATE_ENGINEERING_RFI_PACKET.json').read_text('utf-8'))
        assert len(packet['questions']) == 3
        assert packet['response_received'] is False and packet['approved_financial_rows'] == 0
        assert 'ارسال نشده' in review.designer_reply_status.text()
        assert report == unchanged
        button.click()
        assert 'بازنویسی ممنوع' in review.designer_reply_status.text()
        assert len(list(tmp_path.glob('StructuralPro_RFI_*'))) == 1
    finally:
        dialog.close()


def test_designer_empty_reply_is_receipt_only_not_engineering_approval(qt_app, engineering_report, tmp_path, monkeypatch):
    report = _synthetic_beam_rfi_report(engineering_report)
    unchanged = deepcopy(report)
    dialog = PDFSheetEvidenceDialog(report)
    try:
        review = dialog.graph_review
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getExistingDirectory',
                            lambda *args, **kwargs: str(tmp_path))
        review.findChild(QPushButton, 'PDFDetailExportDesignerRFI').click()
        template, = tmp_path.glob('StructuralPro_RFI_*/DESIGNER_RESPONSE_TEMPLATE.json')
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getOpenFileName',
                            lambda *args, **kwargs: (str(template), 'JSON (*.json)'))
        button = review.findChild(QPushButton, 'PDFDetailInspectDesignerReply')
        assert button is not None and button.isEnabled()
        button.click()
        assert review._designer_reply_receipt['received_evidence_count'] == 0
        assert review._designer_reply_receipt['questions_with_all_evidence_received'] == 0
        assert review._designer_reply_receipt['questions_partially_received'] == 0
        assert '3 بدون پاسخ' in review.designer_reply_status.text()
        export = review.findChild(QPushButton, 'PDFDetailExportDesignerReplyCrosswalk')
        assert export is not None and export.isEnabled()
        destination = tmp_path / 'private-crosswalk.json'
        monkeypatch.setattr('app.pdf_detail_graph_review.QFileDialog.getSaveFileName',
                            lambda *args, **kwargs: (str(destination), 'JSON (*.json)'))
        export.click()
        import json
        crosswalk = json.loads(destination.read_text('utf-8'))
        assert len(crosswalk['evidence_crosswalk']) == 3
        assert crosswalk['approved_financial_rows'] == 0
        assert crosswalk['evidence_crosswalk'][0]['span_axes_unverified'] == 'A-B'
        assert 'متره مالی' in review.designer_reply_status.text()
        original = destination.read_bytes()
        export.click()
        assert 'بازنویسی' in review.designer_reply_status.text()
        assert destination.read_bytes() == original
        assert 'هیچ' not in review.designer_reply_status.text() or 'متره' in review.designer_reply_status.text()
        assert report == unchanged
        assert report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_multidiscipline_gap_review_is_readonly_and_never_approves_boq(qt_app, engineering_report):
    report = deepcopy(engineering_report)
    row = {
        'coverage_id': 'PDF001:p1:family:mechanical',
        'document_id': 'PDF001', 'page': 1,
        'source_pdf_sha256': 'a'*64,
        'candidate_family': 'mechanical', 'sheet_kind': 'UNKNOWN_SHEET_KIND',
        'status': 'UNRESOLVED_CANDIDATE_FAMILY_NO_MEMBER_RECONCILIATION',
        'source_region_ids': ['PDF001:p1:r1:c1'],
        'unassigned_visual_region_ids': ['PDF001:p1:r2:c2'],
        'blocked_region_ids': [],
        'required_review': ['VERIFY_GOVERNING_SHEET_REVISION', 'REVIEW_DETAIL_REGIONS_AND_SCALES'],
        'governing_revision_verified': False,
        'detail_boundary_verified': False,
        'physical_member_count': None,
        'quantity_approval_count': 0, 'financially_payable': False,
    }
    report['multidiscipline_gap_register'] = {
        'coverage_rows': [row], 'acceptance': 'PARTIAL_NO_GO',
        'quantity_approval_count': 0, 'all_trades_reviewed': False,
    }
    before = deepcopy(report)
    dialog = PDFSheetEvidenceDialog(report)
    try:
        review = dialog.graph_review
        idx = _select(review, 'multidiscipline_gaps')
        assert not idx.flags() & Qt.ItemFlag.ItemIsEditable
        assert review.details.isReadOnly()
        detail = review.details.toPlainText()
        for word in ('mechanical', 'UNRESOLVED_CANDIDATE_FAMILY',
                     'VERIFY_GOVERNING_SHEET_REVISION', 'PDF001:p1:r2:c2',
                     'قابل پرداخت مالی — خیر'):
            assert word in detail
        assert report == before
        assert report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()
