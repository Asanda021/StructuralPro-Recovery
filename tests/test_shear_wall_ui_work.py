"""Actual Qt clicks, all specialist actions; explicitly synthetic inputs."""
from copy import deepcopy
from pathlib import Path

def test_full_wall_click_journey(tmp_path,monkeypatch):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox,QTableWidgetItem
 from core.platform.application import StructuralProApp
 from app.shear_wall_detail_editor import open_shear_wall_editor
 from test_shear_wall_work import sample,refresh
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);file=[d['shear_wall_detail']['input_document']['path']];ext=['json'];errors=[];clicked=set()
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(file[0],''));monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(tmp_path/('new-file.'+ext[0])),''));monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.Yes)
 def run():
  dlg=_qt.activeModalWidget();c=dlg.wall_controls
  def click(key):
   b=c[key]
   for i in range(c['tabs'].count()):
    if c['tabs'].widget(i).isAncestorOf(b):c['tabs'].setCurrentIndex(i);break
   _qt.processEvents();QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents();clicked.add(key)
  try:
   assert dlg.layoutDirection()==Qt.RightToLeft
   c['id'].setText('SW1');click('new');assert c['tables']['segments'].rowCount()==0
   click('input_file');click('write_input');assert (tmp_path/'new-file.json').exists()
   click('input_file');file[0]=d['shear_wall_detail']['ownership_document']['path'];click('owner_file')
   for k,v in [('building','B1'),('axis','X-A'),('plan','پلان مصنوعی'),('detail','دیتایل مصنوعی')]:c[k].setText(v)
   for key,t in c['tables'].items():
    count=t.rowCount();click(key+'_add');last=t.rowCount()-1
    QTest.mouseClick(t.viewport(),Qt.LeftButton,pos=t.visualItemRect(t.item(last,0)).center());click(key+'_remove');assert t.rowCount()==count,(key,c['message'].text())
   click('preview');assert 'محاسبه معتبر' in c['message'].text(),c['message'].text();click('save');assert c['state']['revision']==1,c['message'].text();click('load')
   c['reviewer'].setText('بازبین نهایی مستقل');c['note'].setText('کنترل مصنوعی');click('review');assert c['state']['revision']==2,c['message'].text();click('commit');assert a.get_aec_system('P','shear_wall','L1','SW1')['status']=='committed',c['message'].text()
   before=deepcopy(a.open_project('P'));proposal=deepcopy(c['state']['data']);proposal['shear_wall_detail']['input']['segments'][0]['length_m']='6';folder=tmp_path/'revision';folder.mkdir();refresh(proposal,folder)
   t=c['tables']['segments'];t.setItem(0,c['columns']['segments'].index('length_m'),QTableWidgetItem('6'))
   for prefix in ('input','ownership'):
    for f in ('path','sha256','reference'):c[prefix+'_'+f].setText(proposal['shear_wall_detail'][prefix+'_document'][f])
   doc=tmp_path/'reason.txt';doc.write_text('EXPLICIT SYNTHETIC revision');c['evidence_path'].setText(str(doc));c['evidence_ref'].setText('مدرک اصلاح');c['creator'].setText('درخواست‌کننده');c['reason'].setText('اصلاح مستند');click('create_amendment');assert c['amend_id'].text(),c['message'].text();click('review_amendment');click('apply_amendment');assert a.get_aec_system('P','shear_wall','L1','SW1')['revision']==3,c['message'].text();assert a.open_project('P')['takeoffs']==before['takeoffs']
   for f in ('pdf','xlsx','docx','csv'):ext[0]=f;click(f);assert (tmp_path/('new-file.'+f)).exists(),c['message'].text();assert (tmp_path/('new-file.'+f)).stat().st_size>100
   c['new_id'].setText('COPY');c['new_source'].setText('COPY-SOURCE');click('copy');assert a.get_aec_system('P','shear_wall','L1','COPY'),c['message'].text();click('delete');assert a.get_aec_system('P','shear_wall','L1','COPY') is None
   assert {'new','input_file','owner_file','write_input','preview','save','load','review','commit','create_amendment','review_amendment','apply_amendment','copy','delete','pdf','xlsx','docx','csv'}<=clicked
   click('close')
  except Exception as exc:errors.append(repr(exc));dlg.reject()
 QTimer.singleShot(30,run);open_shear_wall_editor(a,project_id='P',floor_id='L1');a.store.close();assert not errors,errors

def test_aec_navigation_opens_specialist(tmp_path,monkeypatch):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QMessageBox
 from core.platform.application import StructuralProApp
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');errors=[]
 monkeypatch.setattr(QMessageBox,'warning',lambda *_:None)
 def parent():
  p=_qt.activeModalWidget()
  def child():
   d=_qt.activeModalWidget()
   try:assert len(d.wall_controls['groups'])==7 and d.wall_controls['tables']['segments'].rowCount()==0
   except Exception as exc:errors.append(repr(exc))
   finally:d.reject()
  try:QTimer.singleShot(30,child);QTest.mouseClick(p.shear_wall_button,Qt.LeftButton)
  except Exception as exc:errors.append(repr(exc))
  finally:p.reject()
 QTimer.singleShot(30,parent);open_reviewed_aec_editor(a,project_id='P',floor_id='L1');a.store.close();assert not errors,errors
