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
