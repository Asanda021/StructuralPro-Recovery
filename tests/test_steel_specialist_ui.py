"""Real offscreen Qt operations; explicitly synthetic schedule, not Windows QA."""
from copy import deepcopy
import pytest
from test_steel_specialist_work import sample,KINDS

@pytest.mark.parametrize('kind',KINDS)
def test_real_full_form_journey(tmp_path,kind,monkeypatch):
 from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog,QTableWidgetItem,QTabWidget
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.steel_detail_editor import open_steel_editor,fill_table
 global _qt
 _qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P');d=sample(kind);errors=[];warnings=[];clicked=[];fmt=[None]
 monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m,*_:warnings.append(str(m)))
 monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.Yes)
 monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(tmp_path/('clicked.'+fmt[0])),''))
 def click(c,key):
  b=c[key];tabs=b.window().findChild(QTabWidget)
  for i in range(tabs.count()):
   if tabs.widget(i).isAncestorOf(b):tabs.setCurrentIndex(i);break
  _qt.processEvents();QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents();clicked.append(key)
 def select(t,row):t.scrollToItem(t.item(row,0));QTest.mouseClick(t.viewport(),Qt.LeftButton,pos=t.visualItemRect(t.item(row,0)).center());_qt.processEvents()
 def run():
  dlg=_qt.activeModalWidget();c=dlg.steel_controls
  try:
   assert dlg.layoutDirection()==Qt.RightToLeft
   assert not c['preview'].isEnabled() and not c['save'].isEnabled()
   c['id'].setText('S1');click(c,'new')
   for k,v in [('building','B1'),('axis','A1'),('source',d['source']['source_id']),('plan','پلان مصنوعی'),('detail','دیتایل مصنوعی')]:c[k].setText(v)
   for group,part in d['steel_detail']['groups'].items():
    c['group'].setCurrentIndex(c['group'].findData(group));_qt.processEvents()
    c['status'].setCurrentIndex(c['status'].findData(part['status']))
    for key,field in [('approver','approved_by'),('group_source','source_ref'),('na_reason','reason')]:c[key].setText(part.get(field,''))
    click(c,'add');select(c['entries'],0);click(c,'remove');assert c['entries'].rowCount()==0
    fill_table(c['entries'],c['columns'],part['entries']);click(c,'store')
   if kind=='steel_deck':
    for key,value in d['steel_detail']['deck'].items():
     if key in c['deck_fields']:c['deck_fields'][key].setText(value)
    click(c,'panel_add');select(c['panels'],0);click(c,'panel_remove');fill_table(c['panels'],c['panel_columns'],d['steel_detail']['deck']['panels'])
   click(c,'preview');assert 'محاسبه معتبر' in c['message'].text(),warnings
   click(c,'save');assert app.get_aec_system('P',kind,'L1','S1')['revision']==1,warnings
   click(c,'load');c['axis'].setText('A2');click(c,'save');assert app.get_aec_system('P',kind,'L1','S1')['revision']==2,warnings
   c['reviewer'].setText('بازبین مستقل');c['note'].setText('کنترل مصنوعی');click(c,'review');click(c,'commit');assert app.get_aec_system('P',kind,'L1','S1')['status']=='committed',warnings
   before=deepcopy(app.open_project('P'))
   if kind=='steel_deck':c['deck_fields']['topping_m'].setText('.07')
   else:
    c['group'].setCurrentIndex(c['group'].findData('columns'));_qt.processEvents();cols=[x[0] for x in c['columns']];c['entries'].setItem(0,cols.index('count'),QTableWidgetItem('3'));click(c,'store')
   e=tmp_path/'revision.txt';e.write_text('EXPLICIT SYNTHETIC revised data');c['evidence_path'].setText(str(e));c['evidence_ref'].setText('مدرک مصنوعی');c['creator'].setText('سازنده');c['reason'].setText('اصلاح مستند مصنوعی');click(c,'create_amendment');assert c['amend_id'].text(),warnings
   click(c,'review_amendment');click(c,'apply_amendment');assert app.get_aec_system('P',kind,'L1','S1')['revision']==4,warnings
   assert app.open_project('P')['takeoffs']==before['takeoffs'] and app.open_project('P')['boq']!=before['boq']
   for ext in ('pdf','xlsx','docx','csv'):fmt[0]=ext;click(c,ext);assert (tmp_path/('clicked.'+ext)).stat().st_size>100,warnings
   c['new_id'].setText('S2');c['new_source'].setText('COPY');click(c,'copy');assert app.get_aec_system('P',kind,'L1','S2'),warnings
   click(c,'delete');assert app.get_aec_system('P',kind,'L1','S2') is None,warnings
   c['id'].setText('S1');click(c,'load');assert not warnings,warnings
   click(c,'delete');assert any('قطعی' in x for x in warnings),warnings
   assert len(clicked)>50
  except Exception as e:errors.append(repr(e))
  finally:dlg.reject()
 QTimer.singleShot(30,run);open_steel_editor(app,project_id='P',floor_id='L1',kind=kind);app.store.close();assert not errors,errors

@pytest.mark.parametrize('kind',KINDS)
def test_existing_aec_navigation_opens_steel_form(tmp_path,kind):
 from PySide6.QtWidgets import QApplication,QComboBox
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P');errors=[]
 def run():
  p=_qt.activeModalWidget()
  try:
   box=next(w for w in p.findChildren(QComboBox) if w.findData(kind)>=0);box.setCurrentIndex(box.findData(kind))
   def child():
    d=_qt.activeModalWidget()
    try:assert d.objectName()=='SteelDetailEditor' and d.steel_controls['kind'].currentData()==kind
    except Exception as e:errors.append(repr(e))
    finally:d.reject()
   QTimer.singleShot(20,child);QTest.mouseClick(p.steel_button,Qt.LeftButton)
  except Exception as e:errors.append(repr(e))
  finally:p.reject()
 QTimer.singleShot(20,run);open_reviewed_aec_editor(app,project_id='P',floor_id='L1');app.store.close();assert not errors,errors
