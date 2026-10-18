"""Actual PySide6 widgets + real application/SQLite; explicit synthetic evidence.

Only the OS file picker is substituted with paths to real fixture files.
Errors are verified through the real dialog's status label; native warning
popups can return without a modal widget in the offscreen Qt platform.
"""
import json
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
from PySide6.QtTest import QTest
from app.bored_pile_detail_editor import open_bored_pile_editor
from app.bored_pile_draft_controller import PileDraftController
from test_bored_pile_real_application_controller import _setup,_ownership,_document

_NATIVE_WARNING=QMessageBox.warning
_qt=None

def test_real_qt_evidence_save_reopen_preview_cas_and_error(tmp_path,monkeypatch):
 global _qt
 _qt=QApplication.instance() or QApplication([])
 app,seed,data=_setup(tmp_path);owner=_document(tmp_path/'owner.json',_ownership(data));chosen=[str(tmp_path/'pile.json')];errors=[];clicked=set()
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(chosen[0],''))
 monkeypatch.setattr(QMessageBox,'warning',_NATIVE_WARNING)
 warnings=[]
 def dismiss():
  box=_qt.activeModalWidget()
  if isinstance(box,QMessageBox):
   warnings.append(box.text());QTest.mouseClick(box.button(QMessageBox.Ok),Qt.LeftButton,pos=box.button(QMessageBox.Ok).rect().center())
 def run():
  dlg=_qt.activeModalWidget();c=dlg.pile_controls
  def click(key):
   _qt.processEvents();QTest.qWait(2);QTest.mouseClick(c[key],Qt.LeftButton,pos=c[key].rect().center());_qt.processEvents();clicked.add(key)
  try:
   assert dlg.layoutDirection()==Qt.RightToLeft;assert not any(k in c for k in ('commit','review','apply_amendment'));click('new')
   assert c['source_mode'].currentData() is None and not c['source_id'].text()
   c['source_mode'].setCurrentIndex(c['source_mode'].findData('manual'))
   for key,value in [('source_id',data['source']['source_id']),('approved_by',data['source']['approved_by']),('measurement_ref',data['source']['source_ref'])]:c[key].setText(value)
   click('input');assert c['piles'].rowCount()==1 and c['rebars'].rowCount()==2
   c['reviewer'].setText('IndependentQtReviewer');c['ownership_claim'].setText('Explicit synthetic audit');c['ownership_reference'].setText('Explicit synthetic ownership');chosen[0]=owner;click('owner');assert c['ownership_sha256'].text()
   click('save');assert c['controller'].revision==1,c['message'].text();click('load');click('preview');report=json.loads(c['report'].toPlainText());assert report['engineering_ready'] and report['ownership_audit'];assert report['ready'] is False and report['commit_allowed'] is False;assert not app.open_project('P')['boq']
   from PySide6.QtWidgets import QStyleOptionViewItem
   for table,columns in [(c['piles'],range(5)),(c['rebars'],range(1,5))]:
    for column in columns:
     option=QStyleOptionViewItem();option.direction=Qt.RightToLeft;table.itemDelegate().initStyleOption(option,table.model().index(0,column));assert option.direction==Qt.LeftToRight
   import os
   if os.environ.get('STRUCTURALPRO_PILE_QA_DIR'):
    qa=Path(os.environ['STRUCTURALPRO_PILE_QA_DIR']);qa.mkdir(parents=True,exist_ok=True);dlg.grab().save(str(qa/'preview.png'));c['tabs'].setCurrentIndex(1);_qt.processEvents();dlg.grab().save(str(qa/'geometry.png'));c['tabs'].setCurrentIndex(2)
   peer=PileDraftController(app,'P');peer.load('FND','PG1');peer.set_preflight(reviewer='PeerReviewer',ownership_reference='Peer synthetic audit');peer.save();assert peer.revision==2
   QTimer.singleShot(10,dismiss);click('save');assert warnings and 'تعارض نسخه' in c['message'].text() and c['controller'].revision==1;assert app.get_structural_member('P','bored_pile','FND','PG1')['revision']==2;click('load');assert c['controller'].revision==2;click('history_refresh');assert c['history'].rowCount()==1
   chosen[0]=str(tmp_path/'bad.json');Path(chosen[0]).write_text('{}');before=c['controller'].data.copy();QTimer.singleShot(10,dismiss);click('input');assert c['message'].text().startswith('خطا:') and c['controller'].data==before
   c['group'].setText('OTHER');QTimer.singleShot(10,dismiss);click('save');assert 'خطا:' in c['message'].text() and c['controller'].revision==2;assert app.get_structural_member('P','bored_pile','FND','PG1')['revision']==2
   c['group'].setText('PG1');original_source=c['source_id'].text();c['source_id'].setText('OTHER-SOURCE');QTimer.singleShot(10,dismiss);click('save');assert 'منبع نمایشی' in c['message'].text() and c['controller'].revision==2;c['source_id'].setText(original_source)
   Path(tmp_path/'pile.json').write_text('{}');click('preview');report=json.loads(c['report'].toPlainText());assert not report['engineering_ready'] and report['blockers'] and 'نامعتبر' in c['message'].text();assert not app.open_project('P')['boq']
   assert {'new','input','owner','save','load','preview','history_refresh'}<=clicked
   click('close')
  except Exception:
   import traceback
   errors.append(traceback.format_exc());dlg.reject()
 QTimer.singleShot(25,run);open_bored_pile_editor(app,project_id='P',floor_id='FND',group_id='PG1');_qt.processEvents();app.store.close();assert not errors,errors

def test_real_structural_menu_opens_persisted_pile_form(tmp_path):
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);app,c,data=_setup(tmp_path);c.save();errors=[];opened=[]
 def parent():
  dlg=_qt.activeModalWidget();widgets=dlg.column_controls
  def child():
   active=_qt.activeModalWidget()
   try:
    controls=active.pile_controls;assert controls['controller'].revision==1;assert controls['piles'].rowCount()==1;assert active.layoutDirection()==Qt.RightToLeft;assert 'commit' not in controls;opened.append(True);QTest.mouseClick(controls['close'],Qt.LeftButton,pos=controls['close'].rect().center())
   except Exception:
    import traceback
    errors.append(traceback.format_exc());active.reject()
  try:
   widgets['kind'].setCurrentIndex(widgets['kind'].findData('bored_pile'));widgets['id'].setText('PG1');widgets['scroll'].ensureWidgetVisible(widgets['pile_specialist']);_qt.processEvents();QTimer.singleShot(20,child);QTest.mouseClick(widgets['pile_specialist'],Qt.LeftButton,pos=widgets['pile_specialist'].rect().center());assert opened
  except Exception:
   import traceback
   errors.append(traceback.format_exc())
  finally:dlg.reject()
 QTimer.singleShot(25,parent);open_manual_structural_editor(app,project_id='P',floor_id='FND');_qt.processEvents();app.store.close();assert opened and not errors,errors
