"""Real native Qt loop; explicit synthetic multi-floor data, no auto approval."""
import sys,os,json
from pathlib import Path
sys.path.insert(0,os.environ.get('CODEX_MANUAL_SOURCE_ROOT',str(Path(__file__).resolve().parents[1])))
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QInputDialog,QMessageBox,QFileDialog
from PySide6.QtCore import QTimer,Qt,QItemSelectionModel,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
from app.manual_takeoff import ManualTakeoffDialog
root=Path(sys.argv[1]);qt=QApplication([]);a=StructuralProApp(root/'db');a.create_project('ساختمان مصنوعی پنج‌طبقه','P')
d=ManualTakeoffDialog(a,'P');d.show();errors=[]
QMessageBox.warning=lambda *args,**kwargs:errors.append(str(args[2]))
result={}
def select(ids):
 d.table.clearSelection()
 for row in range(d.table.rowCount()):
  if d.table.item(row,0).text() in ids:
   idx=d.table.model().index(row,0);d.table.selectionModel().select(idx,QItemSelectionModel.Select|QItemSelectionModel.Rows);d.table.setCurrentCell(row,0,QItemSelectionModel.NoUpdate)
def click(button):QTest.mouseClick(button,Qt.LeftButton);qt.processEvents()
def run():
 try:
  d.floor_id.setText('L1');d.entry_text.setPlainText('ستون: تعداد=1، عرض=0.4، عمق=0.4، ارتفاع=3\nآرماتور: تعداد=2، طول=3، وزن واحد=0.888\nدیوار: تعداد=1، طول=10، ارتفاع=3، بازشو=2')
  click(d.add_button);assert len(d.workbench.records)==3,errors
  originals=d.workbench.records;ids=[r.record_id for r in originals]
  for row in range(d.table.rowCount()):
   record=next(r for r in originals if r.record_id==d.table.item(row,0).text());assert d.table.item(row,4).text()==str(record.quantity)
  select([ids[0]]);click(d.edit_button);assert len(d.workbench.records)==3
  d.entry_text.setPlainText('ستون تعداد=1');click(d.add_button);assert d.workbench.records==originals
  d.entry_text.setPlainText('ستون تعداد=1 عرض=0.4 عمق=0.4 ارتفاع=4');click(d.add_button)
  assert d.workbench.records[0].record_id==ids[0] and d.workbench.records[0].revision==2
  originals=d.workbench.records
  for floor in ['L2','L3','L4','L5']:
   select(ids);QInputDialog.getText=lambda *args,floor=floor,**kwargs:(floor,True);click(d.floor_copy_button)
  assert len(d.workbench.records)==15
  select(ids);click(d.copy_button);assert QApplication.clipboard().text().count('\n')==2
  select(ids);click(d.delete_button);assert len(d.workbench.records)==12
  click(d.undo_button);assert len(d.workbench.records)==15
  click(d.redo_button);assert len(d.workbench.records)==12
  click(d.undo_button);assert len(d.workbench.records)==15
  d.search_field.setText('L3');qt.processEvents();assert sum(not d.table.isRowHidden(i) for i in range(d.table.rowCount()))==3
  assert 'm3:' in d.unit_totals.text() and 'kg:' in d.unit_totals.text() and 'm2:' in d.unit_totals.text()
  d.search_field.clear();click(d.save_button)
  project=a.open_project('P');assert len(project['takeoffs'])==15 and len(project['boq'])==15,len(project['takeoffs'])
  assert {s for row in project['boq'] for s in row['source_ids']}=={r['source_id'] for r in project['takeoffs']}
  byunit={}
  for r in project['boq']:byunit[r['unit']]=byunit.get(r['unit'],0)+r['quantity']
  assert abs(byunit['m3']-3.2)<1e-10 and abs(byunit['kg']-26.64)<1e-10 and byunit['m2']==140
  before=project;click(d.save_button);assert len(a.open_project('P')['takeoffs'])==15
  for fmt,button in [('xlsx',d.export_xlsx_button),('pdf',d.export_pdf_button)]:
   path=root/('manual-fivefloor.'+fmt);QFileDialog.getSaveFileName=lambda *args,path=path,**kwargs:(str(path),'')
   click(button);assert path.is_file() and path.stat().st_size>100,errors
  from openpyxl import load_workbook
  wb=load_workbook(root/'manual-fivefloor.xlsx');assert wb['ریز متره'].sheet_view.rightToLeft;wb.close()
  import pymupdf
  with pymupdf.open(root/'manual-fivefloor.pdf') as pdf:
   assert len(pdf)>=1 and all(page.get_pixmap().width>0 for page in pdf)
   assert str(originals[0].quantity) in '\n'.join(page.get_text() for page in pdf)
  d.grab().save(str(root/'manual-workspace.png'))
  a.create_project('مصنوعی کنترل واگرد نسخه ذخیره‌شده','U')
  second=ManualTakeoffDialog(a,'U');second.show();second.floor_id.setText('L1')
  second.entry_text.setPlainText('ستون تعداد=1 عرض=0.4 عمق=0.4 ارتفاع=3');QTest.mouseClick(second.add_button,Qt.LeftButton);qt.processEvents()
  second.table.selectRow(0);second.table.setCurrentCell(0,0);QTest.mouseClick(second.edit_button,Qt.LeftButton);qt.processEvents()
  second.entry_text.setPlainText('ستون تعداد=1 عرض=0.4 عمق=0.4 ارتفاع=4');QTest.mouseClick(second.add_button,Qt.LeftButton);qt.processEvents()
  assert len(second.workbench.records)==1 and second.workbench.records[0].revision==2
  QTest.mouseClick(second.save_button,Qt.LeftButton);qt.processEvents();saved_records=second.workbench.records
  QTest.mouseClick(second.undo_button,Qt.LeftButton);qt.processEvents()
  assert second.workbench.records==saved_records,'واگرد مقدار ردیف ذخیره‌شده را در پیش‌نمایش تغییر داد'
  second.close();second.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents()
  d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents();a.store.close()
  reopened=StructuralProApp(root/'db');assert reopened.open_project('P')['takeoffs']==before['takeoffs'];reopened.store.close()
  result.update(PASS=True,rows=15,floors=5,units=byunit,negative_errors=errors)
 except BaseException as e:result.update(PASS=False,error=repr(e))
 finally:qt.quit()
QTimer.singleShot(0,run);qt.exec();(root/'qt-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));sys.exit(0 if result.get('PASS') else 1)
