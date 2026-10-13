from PySide6.QtWidgets import QApplication
from core.platform.application import StructuralProApp
from app.manual_takeoff import ManualTakeoffDialog

def test_catalog_formula_real_buttons_save_review_boq_reopen(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([])
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=ManualTakeoffDialog(s,'P');d.show();_qt.processEvents()
 assert hasattr(d,'formula_family'), 'کتابخانه و فرمول به فرم موجود متصل نیست'
 d.manual_tabs.setCurrentIndex(1);_qt.processEvents();assert d.formula_family.count()==86
 d.formula_family.setCurrentIndex(d.formula_family.findData('column'))
 d.formula_id.setText('A');d.formula_source.setText('synthetic:qt:A');d.formula_member.setText('C1');d.floor_id.setText('اول')
 d.formula_unit.setCurrentIndex(d.formula_unit.findData('m3'));d.formula_title.setText('ستون مصنوعی');d.formula_expression.setText('طول*عرض*ارتفاع')
 d.formula_variables.setPlainText('طول=10\nعرض=0.2\nارتفاع=3');d.formula_basis.setText('ابعاد مصنوعی به متر؛ فرمول مستقل');d.formula_reason.setText('ثبت اولیه')
 d.formula_save_button.click();_qt.processEvents();assert s.load_manual_formulas('P')['A']['quantity']==6;assert not s.open_project('P')['boq'];assert d.formula_table.rowCount()==1,d.status.text()
 d.formula_table.setCurrentCell(0,0);d.formula_reviewer.setText('مهندس مصنوعی');d.formula_review_note.setText('واحد و فرمول کنترل شد');d.formula_review_button.click();_qt.processEvents()
 assert s.load_manual_formulas('P')['A']['status']=='reviewed', d.status.text()
 d.formula_table.setCurrentCell(0,0);d.formula_commit_button.click();_qt.processEvents();assert s.open_project('P')['boq'][0]['quantity']==6
 d.close();d.deleteLater();_qt.processEvents();s.store.close()
 s=StructuralProApp(tmp_path);d=ManualTakeoffDialog(s,'P');assert d.formula_table.rowCount()==1;assert d.formula_table.item(0,6).text()=='قطعی';d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_formula_bulk_and_report_buttons_exist(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=ManualTakeoffDialog(s,'P')
 assert hasattr(d,'formula_bulk_button'),'ویرایش گروهی به فرم متصل نیست'
 assert hasattr(d,'formula_floor_copy_button'),'کپی بین طبقات به فرم متصل نیست'
 assert hasattr(d,'formula_xlsx_button') and hasattr(d,'formula_pdf_button'),'خروجی فرمول به فرم متصل نیست'
 d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_bulk_copy_filter_history_with_native_qt_clicks(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt,QTimer
 from test_manual_formula_persistence import data
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 def select():
  d.formula_table.clearSelection();d.formula_table.setFocus();QTest.mouseClick(d.formula_table.viewport(),Qt.LeftButton,pos=d.formula_table.visualItemRect(d.formula_table.item(0,0)).center());_qt.processEvents()
 def click(button):QTest.mouseClick(button,Qt.LeftButton);_qt.processEvents()
 select();d.formula_bulk_name.setText('length');d.formula_bulk_value.setText('5');d.formula_reason.setText('تغییر صریح طول');click(d.formula_bulk_button);assert s.load_manual_formulas('P')['A']['quantity']==3,d.status.text()
 select();d.formula_copy_floor.setText('دوم');d.formula_reason.setText('کپی عضو مستقل');click(d.formula_floor_copy_button);assert len(s.load_manual_formulas('P'))==2,d.status.text()
 d.formula_search.setText('دوم');_qt.processEvents();assert sum(not d.formula_table.isRowHidden(i) for i in range(2))==1
 d.formula_search.clear();_qt.processEvents();select()
 from PySide6.QtTest import QSignalSpy
 spy=QSignalSpy(d.formula_history_button.clicked);click(d.formula_history_button);assert spy.count()==1
 assert any('تغییر صریح طول' in message for title,message in nonblocking_error_dialogs)
 d.grab().save(str(tmp_path/'manual-formula.png'));d.close();d.deleteLater();_qt.processEvents();s.store.close()
