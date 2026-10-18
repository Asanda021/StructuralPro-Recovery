"""Real shared-format reopening on explicitly synthetic documented stairs."""
import csv
import importlib.util
from pathlib import Path
import pytest
from core.platform.application import StructuralProApp
from test_stair_work_stage2 import sample,commit

def test_report_adapter_exists():
 assert importlib.util.find_spec('core.reports.stair_detail_report'), 'Stair report adapter missing'

@pytest.mark.parametrize('fmt',['pdf','xlsx','docx','csv'])
def test_shared_stair_reports_reopen_exact(tmp_path,fmt):
 a=StructuralProApp(tmp_path/'db');a.create_project('پروژه مصنوعی پله','P');d=sample(tmp_path);commit(a,d)
 out=tmp_path/('stair.'+fmt)
 assert hasattr(a,'export_stair_detail_report'),'Stair report service missing'
 a.export_stair_detail_report('P','L1','ST1',out,format=fmt)
 if fmt=='csv':
  assert out.read_bytes().startswith(b'\xef\xbb\xbf');text=out.read_text(encoding='utf-8-sig');assert list(csv.reader(text.splitlines()))
 elif fmt=='xlsx':
  from openpyxl import load_workbook
  w=load_workbook(out);assert all(s.sheet_view.rightToLeft for s in w);text='\n'.join(str(c.value) for s in w for row in s for c in row if c.value is not None);assert any(c.data_type=='n' for s in w for row in s for c in row)
 elif fmt=='docx':
  from docx import Document
  from zipfile import ZipFile
  w=Document(out);text='\n'.join(p.text for p in w.paragraphs)+'\n'+'\n'.join(c.text for t in w.tables for row in t.rows for c in row.cells)
  xml=ZipFile(out).read('word/document.xml');assert b'bidiVisual' in xml and b'w:bidi' in xml
 else:
  import fitz
  w=fitz.open(out);assert len(w)>0 and all(p.rect.width>0 for p in w);text='\n'.join(p.get_text() for p in w)
 # Full 65-digit quantities must survive every file format without rounding.
 exact=a.preview_aec_system('P','stair','L1','ST1')['totals_exact']
 if fmt!='pdf':
  assert 'جمع مهندسی' in text and 'جمع دارای مالکیت' in text
  for v in exact.values():
   if fmt=='xlsx':
    from decimal import Decimal
    assert any(Decimal(str(c.value))==Decimal(v) for sheet in w for row in sheet for c in row if c.value is not None and (c.data_type=='n' or str(c.value)==v))
   else:assert v in text
 assert out.stat().st_size>100;a.store.close()

def test_unknown_ownership_is_not_zero_or_payable(tmp_path):
 from core.reports.stair_detail_report import build
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);d['stair_detail'].pop('ownership_document');a.save_aec_system_draft('P',d)
 rows,metadata=build(a,'P','L1','ST1');assert any('مسدود' in r['description'] for r in rows)
 assert not any(r['description'].startswith('جمع دارای مالکیت') for r in rows)
 assert any(r['description'].startswith('جمع مهندسی') for r in rows)
 unknown=[r for r in rows if r['description'].startswith('مدرک مالکیت؛ مسدود')]
 assert len(unknown)==1 and 'مقدار نامعلوم؛ صفر تلقی نشده است' in unknown[0]['quantity']
 assert unknown[0]['quantity']!='0'
 # A documented zero void area is valid geometry, distinct from unknown ownership.
 assert any('مساحت بازشو' in r['description'] and r['quantity']=='0' for r in rows);a.store.close()

def test_tampered_source_cannot_export(tmp_path):
 from core.reports.stair_detail_report import build
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d);Path(d['stair_detail']['input_document']['path']).write_text('{}')
 with pytest.raises(ValueError):build(a,'P','L1','ST1')
 a.store.close()

def test_four_report_buttons_click_saved_version(tmp_path,monkeypatch):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QFileDialog
 from app.stair_detail_editor import open_stair_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);commit(a,d);errors=[];dest=[None]
 monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(dest[0]),''))
 def run():
  dlg=_qt.activeModalWidget();c=dlg.stair_controls
  try:
   c['id'].setText('ST1');QTest.mouseClick(c['load'],Qt.LeftButton)
   for fmt in ('pdf','xlsx','docx','csv'):
    dest[0]=tmp_path/('clicked.'+fmt);QTest.mouseClick(c['report_'+fmt],Qt.LeftButton);assert dest[0].stat().st_size>100,c['message'].text()
   c['axis'].setText('UNSAVED');dest[0]=tmp_path/'unsaved.pdf';QTest.mouseClick(c['report_pdf'],Qt.LeftButton);assert not dest[0].exists() and 'ذخیره' in c['message'].text()
  except Exception as exc:errors.append(repr(exc))
  finally:dlg.reject()
 QTimer.singleShot(30,run);dlg=open_stair_editor(a,project_id='P',floor_id='L1');dlg.deleteLater();_qt.processEvents();a.store.close();assert not errors,errors

def test_word_persian_logical_alignment(tmp_path):
 from core.reports.exporters import export_docx
 from docx import Document
 from docx.oxml.ns import qn
 path=tmp_path/'rtl.docx';export_docx([{'description':'متن فارسی'}],path)
 d=Document(path)
 for p in d.element.iter(qn('w:pPr')):
  bidi=p.find(qn('w:bidi'));jc=p.find(qn('w:jc'))
  if bidi is not None and bidi.get(qn('w:val'))=='1':assert jc is not None and jc.get(qn('w:val'))=='start'

def test_long_calculation_values_and_hashes_have_standalone_cells(tmp_path):
 from core.reports.stair_detail_report import build
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);commit(a,d)
 rows,_=build(a,'P','L1','ST1');values=[r.get('quantity') for r in rows]
 calc=a.preview_aec_system('P','stair','L1','ST1')['component_calculations'][0]
 assert calc['sloped_length_m'] in values and calc['slope_angle_deg'] in values
 assert d['stair_detail']['input_document']['sha256'] in values
 assert d['stair_detail']['ownership_document']['path'] in values;a.store.close()

def test_excel_summary_does_not_use_narrow_ordinal_column(tmp_path):
 from core.reports.exporters import export_xlsx
 from openpyxl import load_workbook
 p=tmp_path/'summary.xlsx';export_xlsx([{'item_no':1,'description':'مصنوعی','quantity':'1.25'}],p,summary={'amount_by_group':{'جمع مهندسی؛ غیرقابل پرداخت مستقل':'1.25'}},columns=[('item_no','ردیف'),('description','شرح'),('quantity','مقدار')])
 w=load_workbook(p);s=w['ریز متره'];assert 'A4:B4' in {str(r) for r in s.merged_cells.ranges};assert s['C4'].value==1.25
