"""Real Persian Qt/SQLite lifecycle; explicit fixtures, no Windows acceptance."""
from copy import deepcopy
from decimal import Decimal
from importlib import import_module
import pytest

@pytest.mark.parametrize('kind,module,expected',[
 ('paint_finish','test_paint_finish_phase1',['5','5','5','10']),
 ('suspended_ceiling','test_suspended_ceiling_phase1',['20']),
])
def test_real_saved_form_cas_review_commit_duplicate_and_reopen(tmp_path,monkeypatch,kind,module,expected):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QMessageBox
 from core.platform.application import StructuralProApp
 from app.architecture_detail_editor import open_architecture_editor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 app=StructuralProApp(tmp_path/'db');app.create_project('نمونه صریح آزمون رابط','P')
 data=import_module(module).sample();sid=data['system_id']
 app.save_aec_system_draft('P',deepcopy(data),expected_revision=0)
 warnings=[];errors=[]
 monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m:warnings.append(str(m)))
 def click(c,name):
  for i in range(c['tabs'].count()):
   if c['tabs'].widget(i).isAncestorOf(c[name]):c['tabs'].setCurrentIndex(i);break
  QTest.mouseClick(c[name],Qt.LeftButton);_qt.processEvents()
 def run():
  dlg=_qt.activeModalWidget();c=dlg.architecture_controls
  try:
   c['id'].setText(sid);click(c,'load');click(c,'preview')
   assert 'محاسبه معتبر' in c['message'].text()
   click(c,'save');assert not warnings,warnings
   assert app.get_aec_system('P',kind,'L1',sid)['revision']==2
   other=StructuralProApp(tmp_path/'db')
   try:
    changed=deepcopy(data);changed['axis']='محور اصلاح‌شده اتصال دوم'
    other.save_aec_system_draft('P',changed,expected_revision=2)
   finally:other.store.close()
   before=deepcopy(app.open_project('P'));click(c,'save')
   assert warnings and app.open_project('P')==before and not before['boq']
   warnings.clear();click(c,'load')
   c['reviewer'].setText('بازبین مستقل اجرای رابط');c['note'].setText('کنترل مرجع صریح آزمایشی')
   click(c,'review');click(c,'commit');assert not warnings,warnings
   p=deepcopy(app.open_project('P'))
   assert sorted(Decimal(str(r['quantity'])) for r in p['boq'])==sorted(map(Decimal,expected))
   assert all(r['unit']=='m2' for r in p['boq'])
   click(c,'commit');assert warnings and app.open_project('P')==p
  except Exception as exc:errors.append(repr(exc))
  finally:dlg.reject()
 QTimer.singleShot(30,run)
 try:open_architecture_editor(app,project_id='P',floor_id='L1',kind=kind)
 finally:app.store.close()
 assert not errors,errors
 reopened=StructuralProApp(tmp_path/'db')
 try:
  assert reopened.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
  assert not reopened.store.db.execute('pragma foreign_key_check').fetchall()
  assert reopened.get_aec_system('P',kind,'L1',sid)['status']=='committed'
  assert sorted(Decimal(str(r['quantity'])) for r in reopened.open_project('P')['boq'])==sorted(map(Decimal,expected))
 finally:reopened.store.close()
