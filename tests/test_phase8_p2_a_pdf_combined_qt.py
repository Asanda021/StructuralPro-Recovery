"""Synthetic Qt coverage for source-bound PDF evidence review."""
from hashlib import sha256
import json

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

from app.pdf_auto_intake_review import PDFSheetEvidenceDialog


@pytest.fixture(scope='module')
def qt_app():
    return QApplication.instance() or QApplication([])


def test_evidence_link_shows_both_pdf_sources_and_navigates_to_nodes(qt_app):
    plan = {'anchor_id': 'plan-mark', 'document_id': 'PDF001', 'page': 1,
            'bbox_pt': [10, 15, 30, 40], 'kind': 'WORD'}
    detail = {'anchor_id': 'detail-mark', 'document_id': 'PDF002', 'page': 2,
              'bbox_pt': [60, 70, 80, 90], 'kind': 'WORD'}
    report = {
        'documents': [
            {'document_id': 'PDF001', 'source_name': 'plan.pdf', 'sha256': 'a' * 64},
            {'document_id': 'PDF002', 'source_name': 'detail.pdf', 'sha256': 'b' * 64},
        ],
        'page_count': 2,
        'questions': [{'tag': 'PDF_GRAPH_TEST', 'question': 'Supply the governing register',
                       'suggestion': {'status': 'PROPOSED_UNVERIFIED', 'value': None},
                       'evidence': [plan]}],
        'detail_evidence_graph': {
            'graph_sha256': 'c' * 64,
            'quantity_approval_count': 0,
            'pages': [{'document_id': 'PDF001', 'page': 1, 'status': 'BLOCKED',
                       'source_bbox_pt': [0, 0, 600, 500], 'reason': 'Raster source'}],
            'nodes': [
                {'node_id': 'plan-node', 'kind': 'INSTANCE_CANDIDATE', 'label': 'Plan mark C2',
                 'status': 'UNRESOLVED', 'anchors': [plan]},
                {'node_id': 'detail-node', 'kind': 'TYPE_DEFINITION', 'label': 'Detail C2',
                 'status': 'EXAMINED', 'anchors': [detail]},
            ],
            'edges': [
                {'edge_id': 'E1', 'relationship': 'REFERENCES_TYPE', 'status': 'AMBIGUOUS',
                 'source_id': 'plan-node', 'target_id': 'detail-node',
                 'reason': 'Governing revision unknown', 'anchors': [plan]},
                {'edge_id': 'E2', 'relationship': 'REFERENCES_TYPE', 'status': 'BLOCKED',
                 'source_id': 'plan-node', 'target_id': None,
                 'reason': 'Type reference missing', 'anchors': [plan]},
            ],
            'issues': [{'issue_id': 'I1', 'status': 'BLOCKED', 'node_id': 'plan-node',
                        'reason_code': 'REVISION_UNKNOWN', 'reason': 'Revision mismatch',
                        'required_evidence': ['Signed register'], 'anchors': [plan],
                        'review_tag': 'PDF_GRAPH_TEST'}],
        },
    }
    dialog = PDFSheetEvidenceDialog(report)
    review = dialog.graph_review
    try:
        review.tables['documents'].selectRow(1)
        assert 'b' * 64 in review.details.toPlainText()
        review.sections.setCurrentIndex(1)
        review.tables['pages'].selectRow(0)
        assert 'Raster source' in review.details.toPlainText()
        assert '[0, 0, 600, 500]' in review.details.toPlainText()

        review.sections.setCurrentIndex(3)
        review.tables['edges'].selectRow(0)
        selected = review.details.toPlainText()
        assert 'Governing revision unknown' in selected
        assert 'plan.pdf (PDF001) | صفحه 1 | کادر (pt) [10, 15, 30, 40]' in selected
        assert 'detail.pdf (PDF002) | صفحه 2 | کادر (pt) [60, 70, 80, 90]' in selected
        table_model = review.tables['edges'].model()
        assert not table_model.flags(table_model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
        assert review.details.isReadOnly()

        review.filters['nodes'].setText('Plan mark')
        target = review.findChild(QPushButton, 'PDFDetailGraphNavigateTarget')
        target.click()
        assert review.sections.currentIndex() == 2
        assert 'Detail C2' in review.details.toPlainText()
        assert 'detail-mark' in review.details.toPlainText()

        review.sections.setCurrentIndex(3)
        review.tables['edges'].selectRow(1)
        assert 'Type reference missing' in review.details.toPlainText()
        assert not target.isEnabled()

        review.sections.setCurrentIndex(review._section_keys.index('issues'))
        review.tables['issues'].selectRow(0)
        selected = review.details.toPlainText()
        assert all(value in selected for value in ('REVISION_UNKNOWN', 'Revision mismatch', 'Signed register'))
        review.findChild(QPushButton, 'PDFDetailGraphNavigateRelated').click()
        assert 'Plan mark C2' in review.details.toPlainText()
        review.sections.setCurrentIndex(review._section_keys.index('issues'))
        review.question_button.click()
        assert dialog.question_table.currentRow() == 0
        assert dialog.question_action.currentData() == 'request_document'
        dialog.record_question.click()
        saved = dialog.ledger.answers['PDF_GRAPH_TEST']
        assert saved['graph_sha256'] == 'c' * 64
        assert saved['financially_payable'] is False
        assert report['detail_evidence_graph']['quantity_approval_count'] == 0
    finally:
        dialog.close()


def test_revision_attachment_preserves_receipt_for_invalid_or_changed_sources(qt_app, tmp_path, monkeypatch):
    import pymupdf

    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.platform.application import StructuralProApp

    def draw_pdf(path, title):
        with pymupdf.open() as drawing:
            page = drawing.new_page(width=600, height=500)
            page.insert_text((40, 50), title)
            page.draw_rect(pymupdf.Rect(10, 20, 60, 70))
            page.set_rotation(90)
            drawing.save(path)

    source = tmp_path / 'source.pdf'
    draw_pdf(source, 'Beam detail B1')
    original = source.read_bytes()
    register_path = tmp_path / 'register.json'

    def write_register(contents):
        register_path.write_text(json.dumps({
            'schema_version': 1,
            'documents': [{
                'sha256': sha256(contents).hexdigest(), 'project_id': 'P', 'issue_id': 'ISS-1',
                'revision': 'R1', 'status': 'CURRENT', 'authority_reference': 'AUTH-1',
            }],
        }), encoding='utf-8')

    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(source)], ''))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(register_path), ''))
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    service = StructuralProApp(tmp_path / 'project-store')
    service.create_project('Synthetic PDF review', 'P')
    digest = service.store.current_digest('P')
    workspace = GraphicalTakeoffDialog(app_service=service, project_id='P')
    try:
        workspace.auto_pdf_button.click()
        assert not warnings
        previous = workspace._pdf_auto_review_dialog
        previous_report = workspace._pdf_auto_report
        assert previous.isVisible()

        register_path.write_text('{', encoding='utf-8')
        previous.graph_review.attach_button.click()
        assert workspace._pdf_auto_review_dialog is previous
        assert previous.isVisible() and previous.graph_review.attach_status.isVisible()

        draw_pdf(source, 'Beam detail B2')
        write_register(source.read_bytes())
        previous.graph_review.attach_button.click()
        assert workspace._pdf_auto_report is previous_report
        assert 'هش سندهای PDF تغییر کرده است' in previous.graph_review.attach_status.text()
        assert previous.isVisible()

        source.write_bytes(original)
        write_register(original)
        previous.graph_review.attach_button.click()
        latest = workspace._pdf_auto_review_dialog
        assert latest is not previous, previous.graph_review.attach_status.text()
        assert latest.isVisible() and not previous.isVisible()
        assert latest.report['documents'][0]['sha256'] == previous_report['documents'][0]['sha256']
        graph = latest.report['detail_evidence_graph']
        assert graph['graph_sha256'] != previous_report['detail_evidence_graph']['graph_sha256']
        assert graph['quantity_approval_count'] == 0
        qt_app.processEvents()
        review = latest.graph_review
        documents = review.tables['documents']
        QTest.mouseClick(documents.viewport(), Qt.MouseButton.LeftButton,
                         pos=documents.visualRect(documents.model().index(0, 0)).center())
        receipt = review.details.toPlainText()
        assert all(value in receipt for value in ('CURRENT', 'ISS-1', 'R1', 'AUTH-1')), receipt

        review.sections.setCurrentIndex(1)
        pages = review.tables['pages']
        pages.setCurrentIndex(pages.model().index(0, 0))
        page_details = review.details.toPlainText()
        assert 'چرخش — 90' in page_details
        assert 'کادر (pt) [0.0, 0.0, 600.0, 500.0]' in page_details
        review.sections.setCurrentIndex(2)
        review.filters['nodes'].setText('CLOSED_CONTOUR')
        nodes = review.tables['nodes']
        assert nodes.model().rowCount() == 1
        nodes.setCurrentIndex(nodes.model().index(0, 0))
        assert 'کادر (pt) [10.0, 20.0, 60.0, 70.0]' in review.details.toPlainText()

        assert service.store.current_digest('P') == digest
        assert workspace.session.items == []
        assert not warnings
    finally:
        workspace.close()
        qt_app.processEvents()
        service.store.close()



def test_revision_draft_ui_exports_non_authoritative_json_without_overwriting(qt_app, tmp_path, monkeypatch):
    from app.pdf_detail_graph_review import PDFDetailGraphReview
    from core.drawings.pdf_detail_evidence_graph import load_pdf_revision_register

    report = {
        'documents': [{'document_id':'PDF001','source_name':'issued.pdf',
                       'sha256':'d'*64,'page_count':1}],
        'detail_evidence_graph': {
            'nodes':[], 'edges':[], 'issues':[], 'topology_pages':[],
            'pages':[{'document_id':'PDF001','page':1,
                      'printed_revisions':['R3'], 'status':'UNRESOLVED'}],
            'graph_sha256':'a'*64, 'quantity_approval_count':0,
        },
    }
    output=tmp_path/'unverified_draft.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                        lambda *args, **kwargs: (str(output), ''))
    dlg=PDFDetailGraphReview(report)
    try:
        button=dlg.findChild(QPushButton,'PDFDetailExportRevisionRegisterDraft')
        assert button.isEnabled()
        button.click()
        contents=output.read_text(encoding='utf-8')
        parsed=json.loads(contents)
        item=parsed['documents'][0]
        assert item['sha256']=='d'*64
        assert all(item[key] is None for key in (
            'project_id','issue_id','revision','status','authority_reference'))
        with pytest.raises(ValueError):
            load_pdf_revision_register(output)
        assert 'پیش‌نویس' in dlg.export_draft_status.text()
        button.click()
        assert output.read_text(encoding='utf-8')==contents
        assert 'بازنویسی' in dlg.export_draft_status.text()
        assert dlg.tables['documents'].model().rowCount()==1
        assert 'R3' in dlg.tables['documents'].model().data(
            dlg.tables['documents'].model().index(0,6))
        assert report['detail_evidence_graph']['quantity_approval_count']==0
    finally:
        dlg.close()



def test_pdf_auto_ocr_opt_in_is_explicit_and_preserved_when_attaching_register(
        qt_app, tmp_path, monkeypatch):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.platform.application import StructuralProApp
    import core.drawings.pdf_auto_intake as intake

    pdf = tmp_path / 'source.pdf'
    pdf.write_bytes(b'%PDF-1.7 synthetic selector identity, not parsed')
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames',
                        lambda *args: ([str(pdf)], ''))
    arguments = []

    def fake_inspect(sources, **kwargs):
        arguments.append(kwargs)
        return {"fake": True}
    monkeypatch.setattr(intake, 'inspect_pdf_sheet_set', fake_inspect)

    service = StructuralProApp(tmp_path/'store')
    service.create_project('OCR checkbox test', 'P')
    workspace = GraphicalTakeoffDialog(app_service=service, project_id='P')
    try:
        checkbox = workspace.findChild(
            __import__('PySide6.QtWidgets', fromlist=['QCheckBox']).QCheckBox,
            'PDFAutoRenderedOCR',
        )
        assert checkbox is not None and not checkbox.isChecked()
        receipts = []
        monkeypatch.setattr(workspace, '_show_pdf_sheet_evidence',
                            lambda report, source: receipts.append((report, source)))
        workspace.select_pdf_sheet_set()
        assert arguments[-1] == {'rendered_ocr': False}
        checkbox.setChecked(True)
        workspace.select_pdf_sheet_set()
        assert arguments[-1] == {'rendered_ocr': True, 'ocr_language': 'eng'}
        workspace.rendered_ocr_language.setCurrentIndex(1)
        workspace.select_pdf_sheet_set()
        assert arguments[-1] == {'rendered_ocr': True, 'ocr_language': 'eng+fas'}
        assert len(receipts) == 3
    finally:
        workspace.close()
        qt_app.processEvents()
        service.store.close()


def test_reference_links_filter_show_read_only_evidence_and_open_bound_crops(qt_app, tmp_path, monkeypatch):
    import pymupdf
    from PySide6.QtWidgets import QLabel
    from app.pdf_detail_graph_review import PDFDetailGraphReview

    source = tmp_path / 'reference-plan.pdf'
    target = tmp_path / 'reference-detail.pdf'
    documents = []
    for doc_id, path in (('PDF001', source), ('PDF002', target)):
        with pymupdf.open() as drawing:
            page = drawing.new_page(width=200, height=150)
            page.draw_rect([20, 20, 80, 60])
            drawing.save(path)
        documents.append({'document_id': doc_id, 'source_name': path.name, 'page_count': 1,
                          'sha256': sha256(path.read_bytes()).hexdigest()})

    source_anchor = {'anchor_id': 'printed-ref', 'document_id': 'PDF001', 'page': 1,
                     'kind': 'NATIVE_WORD', 'bbox_pt': [15, 15, 85, 65],
                     'source_sha256': documents[0]['sha256'], 'printed': 'Detail D1'}
    target_anchor = {'anchor_id': 'printed-target', 'document_id': 'PDF002', 'page': 1,
                     'kind': 'NATIVE_TITLE', 'bbox_pt': [15, 15, 85, 65],
                     'source_sha256': documents[1]['sha256'], 'printed': 'D1'}
    resolved = {
        'link_id': 'REF-D1', 'source_document_id': 'PDF001', 'source_sheet': 1,
        'source_operator_ids': ['PDF001:p1:d1:s1'], 'source_bbox': source_anchor['bbox_pt'],
        'target_document_id': 'PDF002', 'target_sheet': 1, 'target_bbox': target_anchor['bbox_pt'],
        'reference_text': 'Detail D1', 'link_type': 'PLAN_TO_DETAIL',
        'evidence': [source_anchor, target_anchor], 'revision_status': 'CURRENT',
        'verification_state': 'SOURCE_SUPPORTED', 'financially_payable': False,
    }
    unresolved = {**resolved, 'link_id': 'REF-D9', 'reference_text': 'Detail D9',
                  'target_document_id': None, 'target_sheet': 'UNKNOWN', 'target_bbox': None,
                  'verification_state': 'BLOCKED_MISSING_DOCUMENT', 'evidence': [source_anchor]}
    foreign = {**resolved, 'link_id': 'REF-FOREIGN', 'reference_text': 'Foreign target evidence',
               'evidence': [source_anchor, {**target_anchor, 'source_sha256': 'f' * 64}],
               'verification_state': 'BLOCKED_REVISION'}
    report = {'documents': documents, 'detail_evidence_graph': {
        'nodes': [], 'edges': [], 'issues': [], 'pages': [], 'quantity_approval_count': 0,
        'reference_links': [resolved, unresolved, foreign],
    }}
    widget = PDFDetailGraphReview(report, source_paths={'PDF001': source, 'PDF002': target})
    try:
        key = 'reference_links'
        widget.sections.setCurrentIndex(widget._section_keys.index(key))
        table = widget.tables[key]
        assert widget.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert table.model().rowCount() == 3
        widget.filters[key].setText('SOURCE_SUPPORTED')
        assert table.model().rowCount() == 1
        index = table.model().index(0, 0)
        assert not index.flags() & Qt.ItemFlag.ItemIsEditable
        table.setCurrentIndex(index)
        details = widget.details.toPlainText()
        assert all(value in details for value in (
            'Detail D1', 'PDF001:p1:d1:s1', 'CURRENT', 'SOURCE_SUPPORTED',
            'printed-ref', 'printed-target', 'تأیید مهندسی نشده',
        ))
        assert widget.details.isReadOnly()
        assert not widget.question_button.isEnabled() or widget.question_button.isHidden()
        source_button = widget.component_image_button
        target_button = widget.findChild(QPushButton, 'PDFReferenceShowTargetImage')
        assert source_button.isEnabled() and target_button.isEnabled()
        source_button.click()
        image = widget.findChild(QLabel, 'PDFComponentCropImage')
        assert image is not None and not image.pixmap().isNull()
        assert 'REF-D1' in image.parent().layout().itemAt(0).widget().text()
        target_button.click()
        target_image = widget.findChild(QLabel, 'PDFComponentCropImage')
        assert target_image is not None and not target_image.pixmap().isNull()

        widget.filters[key].setText('UNKNOWN')
        assert table.model().rowCount() == 1
        table.setCurrentIndex(table.model().index(0, 0))
        assert source_button.isEnabled() and not target_button.isEnabled()

        widget.filters[key].setText('BLOCKED_REVISION')
        table.setCurrentIndex(table.model().index(0, 0))
        assert source_button.isEnabled() and not target_button.isEnabled()
        warnings = []
        monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
        source.write_bytes(b'file no longer matches its hash')
        source_button.click()
        assert warnings
        assert report['detail_evidence_graph']['quantity_approval_count'] == 0
        assert all(not row['financially_payable'] for row in report['detail_evidence_graph'][key])
    finally:
        widget.close()
        qt_app.processEvents()
