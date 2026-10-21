"""Actual Qt button journeys on Linux/offscreen; all fixtures explicitly synthetic."""
from copy import deepcopy
import pytest
from test_architecture_specialist_work import sample,KINDS

@pytest.mark.parametrize('kind',KINDS)
def test_real_full_form_journey(tmp_path,kind,monkeypatch):
 from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog,QTableWidgetItem,QTabWidget
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.architecture_detail_editor import open_architecture_editor,fill_table
 global _qt
 _qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P');d=sample(kind);d['architecture_detail']['surfaces'][0]['payment_unit']='m3';errors=[];warnings=[];clicked=[];fmt=[None]
 monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m,*_:warnings.append(str(m)))
 monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.Yes)
 monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(tmp_path/('clicked.'+fmt[0])),''))
 def click(c,key):
  b=c[key];tabs=c['tabs']
  for i in range(tabs.count()):
   if tabs.widget(i).isAncestorOf(b):tabs.setCurrentIndex(i);break
  _qt.processEvents();QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents();clicked.append(key)
 def select(t,row):t.scrollToItem(t.item(row,0));QTest.mouseClick(t.viewport(),Qt.LeftButton,pos=t.visualItemRect(t.item(row,0)).center());_qt.processEvents()
 def run():
  dlg=_qt.activeModalWidget();c=dlg.architecture_controls
  try:
   assert dlg.layoutDirection()==Qt.RightToLeft
   assert not c['preview'].isEnabled() and not c['save'].isEnabled()
   c['id'].setText('W1');click(c,'new')
   for k,v in [('building','B1'),('axis',d['axis']),('source',d['source']['source_id']),('plan','پلان مصنوعی'),('detail','دیتایل مصنوعی')]:c[k].setText(v)
   for key,w in c['geometry_fields'].items():w.setText(d['architecture_detail']['geometry'][key])
   for name,widgets in c['states'].items():
    part=d['architecture_detail'][name]
    for k,w in widgets.items():
     if k=='status':w.setCurrentIndex(w.findData(part[k]))
     else:w.setText(part.get(k,''))
   for name,table in c['tables'].items():
    click(c,name+'_add');select(table,0);click(c,name+'_remove');assert table.rowCount()==0
    fill_table(table,c['columns'][name],d['architecture_detail'][name])
   click(c,'suggest');assert c['proposals'].count()==5 and not app.open_project('P')['boq']
   click(c,'preview');assert 'محاسبه معتبر' in c['message'].text(),warnings
   click(c,'save');assert app.get_aec_system('P',kind,'L1','W1')['revision']==1,warnings
   click(c,'load');c['axis'].setText('اتاق دوم مصنوعی');click(c,'save');assert app.get_aec_system('P',kind,'L1','W1')['revision']==2,warnings
   # Changing project while editing cannot save the captured record into another project.
   app.create_project('مصنوعی دوم','P2');c['project'].setText('P2');click(c,'save');assert warnings and not app.open_project('P2').get('reviewed_aec_systems');warnings.clear();c['project'].setText('P')
   c['reviewer'].setText('بازبین مستقل');c['note'].setText('کنترل مصنوعی');click(c,'review');click(c,'commit');assert app.get_aec_system('P',kind,'L1','W1')['status']=='committed',warnings
   before=deepcopy(app.open_project('P'));table=c['tables']['surfaces'];col=[k for k,t in c['columns']['surfaces']].index('thickness_m');table.setItem(0,col,QTableWidgetItem('.03'))
   e=tmp_path/'revision.txt';e.write_text('EXPLICIT SYNTHETIC revised architecture data');c['evidence_path'].setText(str(e));c['evidence_ref'].setText('مدرک مصنوعی');c['creator'].setText('سازنده');c['reason'].setText('اصلاح مستند مصنوعی');click(c,'create_amendment');assert c['amend_id'].text(),warnings
   assert any(c['amendment_grid'].item(r,3).text()=='0.1131' for r in range(c['amendment_grid'].rowCount()))
   c['id'].setText('UNRELATED');click(c,'review_amendment');assert warnings;warnings.clear();c['id'].setText('W1')
   click(c,'review_amendment');click(c,'apply_amendment');assert app.get_aec_system('P',kind,'L1','W1')['revision']==4,warnings
   assert app.open_project('P')['takeoffs']==before['takeoffs'] and app.open_project('P')['boq']!=before['boq']
   applied=c['amend_id'].text();c['amend_id'].clear();c['amendment_grid'].setRowCount(0);click(c,'load');assert c['amend_id'].text()==applied and c['amendment_grid'].rowCount()>0
   for ext in ('pdf','xlsx','docx','csv'):fmt[0]=ext;click(c,ext);assert (tmp_path/('clicked.'+ext)).stat().st_size>100,warnings
   c['new_id'].setText('W2');c['new_source'].setText('COPY');click(c,'copy');copied=app.get_aec_system('P',kind,'L1','W2');assert copied,warnings
   a=copied['data']['architecture_detail'];assert a['geometry']['physical_wall_id']!='WALL-1'
   if a['unit_regions']:assert a['unit_regions'][0]['layer_id']==a['masonry_layers'][0]['id']
   click(c,'delete');assert app.get_aec_system('P',kind,'L1','W2') is None,warnings
   c['id'].setText('W1');click(c,'load');assert not warnings,warnings
   click(c,'delete');assert any('قطعی' in x for x in warnings),warnings
   assert set(['new','load','save','preview','review','commit','suggest','copy','delete','create_amendment','review_amendment','apply_amendment','pdf','xlsx','docx','csv']+[n+s for n in c['tables'] for s in ('_add','_remove')])<=set(clicked)
  except Exception as e:errors.append(repr(e))
  finally:dlg.reject()
 QTimer.singleShot(30,run);open_architecture_editor(app,project_id='P',floor_id='L1',kind=kind);app.store.close();assert not errors,errors

@pytest.mark.parametrize('kind',KINDS)
def test_existing_aec_navigation_opens_architecture_form(tmp_path,kind):
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
    try:assert d.objectName()=='ArchitectureDetailEditor' and d.architecture_controls['kind'].currentData()==kind
    except Exception as e:errors.append(repr(e))
    finally:d.reject()
   QTimer.singleShot(20,child);QTest.mouseClick(p.architecture_button,Qt.LeftButton)
  except Exception as e:errors.append(repr(e))
  finally:p.reject()
 QTimer.singleShot(20,run);open_reviewed_aec_editor(app,project_id='P',floor_id='L1');app.store.close();assert not errors,errors
