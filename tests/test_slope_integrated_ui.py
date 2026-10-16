"""Real Linux/offscreen Qt floor operations; explicitly synthetic records."""
from copy import deepcopy

def test_slope_full_click_journey(tmp_path,monkeypatch):
 from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog,QComboBox,QTableWidgetItem
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.architecture_detail_editor import open_architecture_editor,fill_table
 from test_slope_integrated_work import sample
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی کف','P');d=sample(tmp_path);errors=[];warnings=[];clicked=set();fmt=[None]
 monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m,*_:warnings.append(str(m)));monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.Yes);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(tmp_path/('floor.'+fmt[0])),''))
 def click(c,key):
  b=c[key]
  for i in range(c['tabs'].count()):
   if c['tabs'].widget(i).isAncestorOf(b):c['tabs'].setCurrentIndex(i);break
  _qt.processEvents();QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents();clicked.add(key)
 def run():
  dlg=_qt.activeModalWidget();c=dlg.architecture_controls
  try:
   assert c['kind'].currentData()=='floor_finish' and dlg.layoutDirection()==Qt.RightToLeft
   assert dlg.height()<=900, 'Geometry must scroll within the dialog rather than hide action buttons below the screen'
   c['id'].setText('S1');click(c,'new');assert all(not w.text() for k,w in c['geometry_fields'].items() if k in ('length_m','width_m','base_level_m','count'))
   for k,v in [('building','B1'),('axis',d['axis']),('source',d['source']['source_id']),('plan','پلان مصنوعی'),('detail','دیتایل مصنوعی')]:c[k].setText(v)
   for k,w in c['geometry_fields'].items():
    if isinstance(w,QComboBox):w.setCurrentIndex(w.findData(d['architecture_detail']['geometry'][k]))
    else:w.setText(d['architecture_detail']['geometry'][k])
   for name,t in c['tables'].items():
    click(c,name+'_add');item=t.item(0,0);QTest.mouseClick(t.viewport(),Qt.LeftButton,pos=t.visualItemRect(item).center());click(c,name+'_remove');assert t.rowCount()==0;fill_table(t,c['columns'][name],d['architecture_detail'][name]);assert all(t.columnWidth(i)>=t.horizontalHeader().fontMetrics().horizontalAdvance(label) for i,(key,label) in enumerate(c['columns'][name])), 'Column headers must remain readable by horizontal scrolling'
   click(c,'suggest');assert c['proposals'].count()>=3 and not a.open_project('P')['boq']
   click(c,'preview');assert 'محاسبه معتبر' in c['message'].text(),warnings;click(c,'save');click(c,'load');assert a.get_aec_system('P','floor_finish','L1','S1')['revision']==1,warnings
   c['axis'].setText('فضای مستقل اصلاح‌شده');click(c,'save');c['reviewer'].setText('بازبین مستقل');c['note'].setText('کنترل مصنوعی');click(c,'review');click(c,'commit');assert a.get_aec_system('P','floor_finish','L1','S1')['status']=='committed',warnings;before=deepcopy(a.open_project('P'))
   table=c['tables']['zones'];fields=[k for k,t in c['columns']['zones']]
   for key,value in [('thickness_00_m','.3'),('thickness_10_m','.4'),('thickness_01_m','.5')]:table.setItem(0,fields.index(key),QTableWidgetItem(value))
   e=tmp_path/'rev.txt';e.write_text('EXPLICIT SYNTHETIC revised floor stratum');c['creator'].setText('سازنده');c['reason'].setText('اصلاح مستند مصنوعی');c['evidence_path'].setText(str(e));c['evidence_ref'].setText('مدرک مصنوعی');click(c,'create_amendment');assert c['amend_id'].text(),warnings;click(c,'review_amendment');click(c,'apply_amendment');assert a.get_aec_system('P','floor_finish','L1','S1')['revision']==4,warnings
   assert a.open_project('P')['takeoffs']==before['takeoffs'] and a.open_project('P')['boq']!=before['boq'];assert any(c['amendment_grid'].item(i,3).text()=='1.9' for i in range(c['amendment_grid'].rowCount()))
   for ext in ('pdf','xlsx','docx','csv'):fmt[0]=ext;click(c,ext);assert (tmp_path/('floor.'+ext)).stat().st_size>100,warnings
   c['new_id'].setText('F2');c['new_source'].setText('COPY');click(c,'copy');assert a.get_aec_system('P','floor_finish','L1','F2'),warnings;click(c,'delete');assert a.get_aec_system('P','floor_finish','L1','F2') is None,warnings
   assert not warnings,warnings;assert {'new','save','load','review','commit','preview','suggest','create_amendment','review_amendment','apply_amendment','copy','delete','zones_add','zones_remove','openings_add','openings_remove','pdf','xlsx','docx','csv'}<=clicked
  except Exception as exc:errors.append(repr(exc))
  finally:dlg.reject()
 QTimer.singleShot(30,run);open_architecture_editor(a,project_id='P',floor_id='L1',kind='floor_finish',specialism='slope');a.store.close();assert not errors,errors


def test_aec_navigation_opens_slope_form(tmp_path):
 from PySide6.QtWidgets import QApplication,QComboBox
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');errors=[]
 def run():
  p=_qt.activeModalWidget()
  try:
   box=next(w for w in p.findChildren(QComboBox) if w.findData('floor_finish')>=0);box.setCurrentIndex(box.findData('floor_finish'))
   def child():
    d=_qt.activeModalWidget()
    try:assert 'zones' in d.architecture_controls['tables']
    except Exception as exc:errors.append(repr(exc))
    finally:d.reject()
   QTimer.singleShot(25,child);QTest.mouseClick(p.slope_button,Qt.LeftButton)
  except Exception as exc:errors.append(repr(exc))
  finally:p.reject()
 QTimer.singleShot(20,run);open_reviewed_aec_editor(a,project_id='P',floor_id='L1');a.store.close();assert not errors,errors
