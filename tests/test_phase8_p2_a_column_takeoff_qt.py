"""Qt review UI: actual user click flow with source and assumed steel scenarios."""
from hashlib import sha256
import pytest
from PySide6.QtWidgets import QApplication

from app import pdf_column_takeoff_panel as ui


@pytest.fixture(scope='module')
def qapp():
    app=QApplication.instance() or QApplication([])
    return app


def _fake_schedule(content):
    return {'status':'DRAFT_COMPLETE_GRID_EVIDENCE',
            'document_sha256':sha256(content).hexdigest(),
            'plan_page':14,'page_count':19,'grid_node_count':15,'draft_node_count':15,
            'draft_extended_length_total_m':'169.70',
            'groups':[
                {'type_tag':'C1','grid_location_candidates':11,'printed_type_length_m':'10.70','draft_extended_length_m':'117.70'},
                {'type_tag':'C2','grid_location_candidates':2,'printed_type_length_m':'14.00','draft_extended_length_m':'28.00'},
                {'type_tag':'C3','grid_location_candidates':2,'printed_type_length_m':'12.00','draft_extended_length_m':'24.00'},
            ],
            'rows':[{'candidate_id':f'PDF001:p14:r1:c{x}', 'grid_row':1, 'grid_column':x,
                     'plan_page':14,'detail_page':19,'type_tag':'C1','x_pt':100+x,'y_pt':100,
                     'printed_length_m':'10.70','printed_dimension_text':'L=10.70 m',
                     'source_operator_ids':[f'PDF001:p14:d{x}:s1'],
                     'status':'DRAFT_TYPE_LENGTH_CANDIDATE'} for x in range(1,16)]}


def test_ui_extract_15_rows_edit_scenario_and_calculate(monkeypatch,tmp_path,qapp):
    file=tmp_path/'sample.pdf';file.write_bytes(b'%PDF-1.4 fake synthetic qt unit')
    monkeypatch.setattr(ui,'draft_column_length_schedule',lambda path: _fake_schedule(file.read_bytes()))
    panel=ui.PDFColumnTakeoffPanel(source_paths={'PDF001':str(file)})
    try:
        panel.extract_button.click()
        assert panel.positions.rowCount()==15
        assert panel.assumptions.rowCount()==3
        assert panel.weight_preview is None
        assert not panel.scenario_ack.isChecked()
        panel.positions.setCurrentCell(1, 0)
        evidence = panel.position_evidence.toPlainText()
        assert all(witness in evidence for witness in (
            'شیت پلان: 14', 'شیت دیتیل: 19', 'L=10.70 m', 'PDF001:p14:d2:s1',
        ))
        panel.scenario_ack.setChecked(True)
        panel.weight_button.click()
        assert panel.weight_preview['draft_weight_total_kg']=='5362.520'
        assert not panel.weight_preview['financially_payable']
        assert panel.weight_rows.rowCount()==3
    finally:
        panel.close()


def test_ui_rejects_changed_pdf_after_extract(monkeypatch,tmp_path,qapp):
    file=tmp_path/'sample.pdf';file.write_bytes(b'%PDF-1.4 original')
    monkeypatch.setattr(ui,'draft_column_length_schedule',lambda path: _fake_schedule(b'%PDF-1.4 original'))
    panel=ui.PDFColumnTakeoffPanel(source_paths={'PDF001':str(file)})
    try:
        panel.extract()
        panel.scenario_ack.setChecked(True)
        file.write_bytes(b'%PDF-1.4 modified')
        panel.compute_weight()
        assert panel.weight_preview is None
        assert 'تغییر' in panel.weight_receipt.text()
    finally:
        panel.close()


def test_ui_xlsx_export_is_real_but_no_boq(monkeypatch,tmp_path,qapp):
    from openpyxl import load_workbook

    file=tmp_path/'sample.pdf';file.write_bytes(b'%PDF-1.4 synthetic')
    monkeypatch.setattr(ui,'draft_column_length_schedule',lambda path:_fake_schedule(file.read_bytes()))
    panel=ui.PDFColumnTakeoffPanel(source_paths={'PDF001':str(file)})
    try:
        panel.extract()
        panel.scenario_ack.setChecked(True)
        panel.compute_weight()
        dest=tmp_path/'preview.xlsx'
        monkeypatch.setattr(ui.QFileDialog,'getSaveFileName',lambda *a,**k:(str(dest),'Excel (*.xlsx)'))
        monkeypatch.setattr(ui.QMessageBox,'information',lambda *a,**k:None)
        panel.export()
        assert dest.exists()
        assert dest.stat().st_size>1500
        assert str(dest) in panel.export_receipt.text()
        workbook = load_workbook(dest, data_only=False, read_only=True)
        try:
            assert workbook['Types']['H2'].data_type == 'f'
            assert workbook['Preview']['B6'].value == 'NO'
            assert 'PDF001:p14:d1:s1' in workbook['PDF positions']['K2'].value
        finally:
            workbook.close()
    finally:
        panel.close()


def test_ui_invalidates_weight_after_assumption_edit_or_acknowledgment_change(monkeypatch, tmp_path, qapp):
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'%PDF-1.4 synthetic')
    monkeypatch.setattr(ui, 'draft_column_length_schedule',
                        lambda path, **kwargs: _fake_schedule(source.read_bytes()))
    panel = ui.PDFColumnTakeoffPanel(source_paths={'PDF001': source})
    try:
        panel.extract_button.click()
        assert panel.schedule and panel.positions.rowCount() == 15
        assert not panel.weight_button.isEnabled() and not panel.export_button.isEnabled()
        panel.scenario_ack.setChecked(True)
        panel.weight_button.click()
        assert panel.weight_preview and panel.export_button.isEnabled()
        assert panel.weight_rows.rowCount() == 3

        panel.assumptions.item(0, 5).setText('invalid')
        assert panel.weight_preview is None
        assert not panel.export_button.isEnabled() and panel.weight_rows.rowCount() == 0
        assert panel.positions.rowCount() == 15
        panel.weight_button.click()
        assert 'نامعتبر' in panel.weight_receipt.text()

        panel.assumptions.item(0, 5).setText('19.1')
        assert panel.export_button.isEnabled()
        assert panel.weight_preview['groups'][0]['profile_unit_mass_kg_m'] == '19.1'
        panel.assumptions.item(0, 4).setText('3')
        assert panel.weight_preview['groups'][0]['profile_count_per_location'] == 3
        panel.scenario_ack.setChecked(False)
        assert not panel.weight_button.isEnabled() and not panel.export_button.isEnabled()
        assert panel.weight_preview is None and panel.weight_rows.rowCount() == 0
    finally:
        panel.close()


def test_ui_source_setter_clears_previous_results_and_pins_reviewed_hash(monkeypatch, tmp_path, qapp):
    first, second = (tmp_path / name for name in ('first.pdf', 'second.pdf'))
    first.write_bytes(b'%PDF-1.4 first')
    second.write_bytes(b'%PDF-1.4 second')
    calls = []

    def extract(path, *, expected_sha256=None):
        calls.append((path, expected_sha256))
        result = _fake_schedule(path.read_bytes())
        if expected_sha256 and expected_sha256 != result['document_sha256']:
            raise ValueError('PDF SHA256 does not match the reviewed source')
        return result

    monkeypatch.setattr(ui, 'draft_column_length_schedule', extract)
    panel = ui.PDFColumnTakeoffPanel()
    try:
        assert not panel.extract_button.isEnabled()
        panel.set_source(first)
        assert str(first) in panel.source_label.text()
        assert not calls
        panel.extract_button.click()
        panel.scenario_ack.setChecked(True)
        panel.weight_button.click()
        assert panel.export_button.isEnabled()

        expected = sha256(second.read_bytes()).hexdigest()
        panel.set_source(second, expected_sha256=expected)
        assert str(second) in panel.source_label.text()
        assert panel.schedule is None and panel.weight_preview is None
        assert panel.positions.rowCount() == panel.assumptions.rowCount() == panel.weight_rows.rowCount() == 0
        assert not panel.scenario_ack.isChecked() and not panel.export_button.isEnabled()
        assert len(calls) == 1
        second.write_bytes(b'%PDF-1.4 changed')
        panel.extract_button.click()
        assert calls[-1] == (second, expected)
        assert 'ناموفق' in panel.receipt.text()
        assert panel.schedule is None
    finally:
        panel.close()


def test_ui_rechecks_source_after_save_dialog_returns(monkeypatch, tmp_path, qapp):
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'%PDF-1.4 synthetic')
    monkeypatch.setattr(ui, 'draft_column_length_schedule',
                        lambda path, **kwargs: _fake_schedule(source.read_bytes()))
    panel = ui.PDFColumnTakeoffPanel(source_paths={'PDF001': source})
    try:
        panel.extract_button.click()
        panel.scenario_ack.setChecked(True)
        panel.weight_button.click()
        assert panel.export_button.isEnabled()
        destination = tmp_path / 'stale.xlsx'

        def save_dialog(*args, **kwargs):
            source.write_bytes(b'%PDF-1.4 changed while dialog was open')
            return str(destination), 'Excel (*.xlsx)'

        monkeypatch.setattr(ui.QFileDialog, 'getSaveFileName', save_dialog)
        monkeypatch.setattr(ui.QMessageBox, 'information', lambda *args, **kwargs: None)
        panel.export_button.click()
        assert not destination.exists()
        assert panel.schedule is None and panel.weight_preview is None
        assert panel.positions.rowCount() == panel.weight_rows.rowCount() == 0
        assert not panel.export_button.isEnabled()
        assert 'تغییر' in panel.weight_receipt.text()
    finally:
        panel.close()
