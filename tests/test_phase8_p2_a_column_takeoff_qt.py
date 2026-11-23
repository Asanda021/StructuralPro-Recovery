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
            'plan_page':14,'grid_node_count':15,'draft_node_count':15,
            'draft_extended_length_total_m':'169.70',
            'groups':[
                {'type_tag':'C1','grid_location_candidates':11,'printed_type_length_m':'10.70','draft_extended_length_m':'117.70'},
                {'type_tag':'C2','grid_location_candidates':2,'printed_type_length_m':'14.00','draft_extended_length_m':'28.00'},
                {'type_tag':'C3','grid_location_candidates':2,'printed_type_length_m':'12.00','draft_extended_length_m':'24.00'},
            ],
            'rows':[{'candidate_id':f'PDF001:p14:r1:c{x}', 'grid_row':1, 'grid_column':x,
                     'plan_page':14,'type_tag':'C1','x_pt':100+x,'y_pt':100,'printed_length_m':'10.70',
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
    finally:
        panel.close()