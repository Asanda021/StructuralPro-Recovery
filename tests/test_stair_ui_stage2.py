"""Real modal Qt clicks on explicit synthetic stairs."""
from pathlib import Path
from copy import deepcopy
import importlib.util

def test_stair_editor_exists():
 assert importlib.util.find_spec('app.stair_detail_editor') is not None,'Typed stair editor missing'

def test_full_stair_click_journey(tmp_path,monkeypatch):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox,QTableWidgetItem
 from app.stair_detail_editor import open_stair_editor
 from core.platform.application import StructuralProApp
 from test_stair_work_stage2 import sample,refresh
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);file=[d['stair_detail']['input_document']['path']];errors=[];clicked=set()
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(file[0],''));monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(tmp_path/'new-input.json'),''));monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.Yes)
 def run():
  dlg=_qt.activeModalWidget();c=dlg.stair_controls
  def click(k):
   b=c[k]
   for i in range(c['tabs'].count()):
    if c['tabs'].widget(i).isAncestorOf(b):c['tabs'].setCurrentIndex(i);break
   _qt.processEvents();QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents();clicked.add(k)
  try:
   assert dlg.layoutDirection()==Qt.RightToLeft;c['id'].setText('ST1');click('new');assert all(t.rowCount()==0 for t in c['tables'].values());assert not c['metadata']['story_height_m'].text()
   click('input_file');file[0]=d['stair_detail']['ownership_document']['path'];click('owner_file')
   for k,v in [('building','B1'),('axis','A-1'),('source','SRC-ST1'),('author','تهیه‌کننده مصنوعی'),('measurement','برداشت صریحاً مصنوعی'),('plan','پلان مصنوعی'),('detail','دیتایل مصنوعی')]:c[k].setText(v)
   for k,t in c['tables'].items():
    n=t.rowCount();click(k+'_add');last=t.rowCount()-1;t.scrollToItem(t.item(last,0));_qt.processEvents();QTest.mouseClick(t.viewport(),Qt.LeftButton,pos=t.visualItemRect(t.item(last,0)).center());click(k+'_remove');assert t.rowCount()==n,(k,c['message'].text())
   click('preview');assert c['summary'].rowCount()>20,c['message'].text();click('save');assert c['state']['revision']==1,c['message'].text();click('load');c['reviewer'].setText('بازبین نهایی');c['note'].setText('کنترل مستقل');click('review');assert c['state']['revision']==2,c['message'].text();click('commit');assert a.get_aec_system('P','stair','L1','ST1')['status']=='committed',c['message'].text()
   old=deepcopy(a.open_project('P'));proposal=deepcopy(c['state']['data']);proposal['stair_detail']['input']['rebars'][0]['straight_m']='4';folder=tmp_path/'rev';folder.mkdir();refresh(proposal,folder)
   t=c['tables']['rebars'];t.setItem(0,c['columns']['rebars'].index('straight_m'),QTableWidgetItem('4'))
   for prefix in ('input','ownership'):
    for f in ('path','sha256','reference'):c[prefix+'_'+f].setText(proposal['stair_detail'][prefix+'_document'][f])
   p=tmp_path/'reason.txt';p.write_text('Explicit synthetic revision');c['evidence_path'].setText(str(p));c['evidence_ref'].setText('مدرک اصلاحی');c['creator'].setText('درخواست‌کننده');c['reason'].setText('اصلاح مستند');click('create_amendment');assert c['amend_id'].text(),c['message'].text();click('review_amendment');click('apply_amendment');click('history_refresh');assert c['history'].rowCount()==1;assert a.get_aec_system('P','stair','L1','ST1')['revision']==3,c['message'].text();assert a.open_project('P')['takeoffs']==old['takeoffs']
   c['new_id'].setText('COPY');c['new_source'].setText('SRC-COPY');click('copy');assert a.get_aec_system('P','stair','L1','COPY'),c['message'].text();click('delete');assert a.get_aec_system('P','stair','L1','COPY') is None;click('history_refresh');assert c['history'].rowCount()==2,c['message'].text()
   click('load');file[0]=d['stair_detail']['input_document']['path'];click('input_file');click('write_input');assert (tmp_path/'new-input.json').is_file();click('close')
   assert {'new','input_file','owner_file','write_input','preview','save','load','review','commit','copy','delete','create_amendment','review_amendment','apply_amendment','history_refresh','close'}<=clicked
  except Exception as exc:errors.append(repr(exc));dlg.reject()
 QTimer.singleShot(30,run);dlg=open_stair_editor(a,project_id='P',floor_id='L1');a.store.close();dlg.deleteLater();_qt.processEvents();assert not errors,errors

def test_aec_navigation_opens_stair_form(tmp_path,monkeypatch):
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
   try:assert len(d.stair_controls['tables'])==7 and not d.stair_controls['metadata']['story_height_m'].text()
   except Exception as exc:errors.append(repr(exc))
   finally:d.reject()
  try:QTimer.singleShot(30,child);QTest.mouseClick(p.stair_button,Qt.LeftButton)
  except Exception as exc:errors.append(repr(exc))
  finally:p.reject()
 QTimer.singleShot(30,parent);open_reviewed_aec_editor(a,project_id='P',floor_id='L1');a.store.close();_qt.processEvents();assert not errors,errors
