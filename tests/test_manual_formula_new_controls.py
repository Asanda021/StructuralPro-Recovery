from PySide6.QtWidgets import QApplication
from core.platform.application import StructuralProApp
from app.manual_takeoff import ManualTakeoffDialog

def test_controls_present_in_existing_manual_dialog(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=ManualTakeoffDialog(s,'P')
 assert d.formula_table is d.table, 'دو جدول جدا برای متره و فرمول وجود دارند'
 assert hasattr(d,'formula_amend_button'), 'گردش اصلاح قطعی در UI موجود نیست'
 assert hasattr(d,'deduction_save_button') and hasattr(d,'deduction_delete_button'), 'فرم کسورات متصل نیست'
 assert hasattr(d,'formula_delete_button') and hasattr(d,'formula_undo_button') and hasattr(d,'formula_redo_button'), 'دفتر فرمول یکپارچه نیست'
 d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_native_click_deductions_history_and_committed_amendment(tmp_path):
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt
 from test_manual_formula_amendments import base
 from test_manual_formula_persistence import data
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=base(tmp_path/'db');s.save_manual_formula('P','W',data(family='block_wall',member='W1',source_id='wall:synthetic',unit='m2',expression='طول*ارتفاع',variables={'طول':'10','ارتفاع':'3'}),expected_revision=0,reason='دیوار')
 d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 def select(key):
  r=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).text()==key);d.table.scrollToItem(d.table.item(r,0));_qt.processEvents();QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(r,0)).center());_qt.processEvents()
 def click(button):
  if button.parent() is not d:d.formula_scroll.ensureWidgetVisible(button)
  _qt.processEvents();QTest.mouseClick(button,Qt.LeftButton);_qt.processEvents()
 select('W');d.deduction_source.setText('opening:1');d.deduction_variable.setText('بازشو');d.deduction_quantity.setText('2');d.deduction_unit.setCurrentIndex(d.deduction_unit.findData('m2'));d.deduction_basis.setText('هندسه مصنوعی صریح 1×2متر');d.formula_reason.setText('کسر بازشو');click(d.deduction_save_button);assert s.load_manual_formulas('P')['W']['quantity']==28,d.status.text()
 select('W');d.deduction_quantity.setText('3');d.formula_reason.setText('هندسه اصلاح‌شده');click(d.deduction_save_button);assert s.load_manual_formulas('P')['W']['quantity']==27,d.status.text()
 select('W');click(d.deduction_delete_button);assert s.load_manual_formulas('P')['W']['quantity']==30
 click(d.formula_undo_button);assert s.load_manual_formulas('P')['W']['quantity']==27;click(d.formula_redo_button);assert s.load_manual_formulas('P')['W']['quantity']==30
 select('W');click(d.formula_delete_button);assert 'W' not in s.load_manual_formulas('P');click(d.formula_undo_button);assert 'W' in s.load_manual_formulas('P')
 select('A');click(d.formula_load_button);d.formula_variables.setPlainText('length=5\nwidth=0.2\nheight=3');d.formula_creator.setText('سازنده');d.formula_reason.setText('اصلاح طول قطعی');select('A');click(d.formula_amend_button);assert d.formula_amend_id.text(),d.status.text();assert s.open_project('P')['boq'][0]['quantity']==6
 d.formula_reviewer.setText('بازبین مستقل');d.formula_review_note.setText('فرمول و مبنا کنترل شد');click(d.formula_amend_review_button);click(d.formula_amend_apply_button);assert s.open_project('P')['boq'][0]['quantity']==3,d.status.text();assert s.open_project('P')['takeoffs'][0]['quantities'][0]['amount']==6
 d.grab().save(str(tmp_path/'new-controls.png'));d.close();d.deleteLater();_qt.processEvents();s.store.close()
