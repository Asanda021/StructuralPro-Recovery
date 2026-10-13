from core.takeoff.manual_workbench import ManualTakeoffWorkbench

def test_pending_specialized_move_copy_and_undo_preserve_quantity_and_identity():
 w=ManualTakeoffWorkbench('P');r=w.add_text('ستون: تعداد=1، عرض=0.5، عمق=0.5، ارتفاع=3',floor_id='اول',element_label='C1')
 assert callable(getattr(w,'relocate_records',None)), 'ورودی تخصصی هنوز انتقال یکپارچه ندارد'
 moved=w.relocate_records([r.record_id],floor='دوم',block='بلوک۲',location='آکس۲',mode='move')[0];assert moved.record_id==r.record_id and moved.revision==2 and moved.quantity==r.quantity
 copied=w.relocate_records([r.record_id],floor='سوم',block='بلوک۲',location='آکس۲',mode='copy')[0];assert copied.record_id!=r.record_id and copied.quantity==r.quantity
 w.undo();assert len(w.records)==1;w.undo();assert w.records[0]==r

def test_native_pending_specialized_move_then_sqlite_save(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.manual_takeoff import ManualTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=ManualTakeoffDialog(s,'P');d.show();d.floor_id.setText('اول');d.element_label.setText('C1');d.entry_text.setPlainText('ستون: تعداد=1، عرض=0.5، عمق=0.5، ارتفاع=3');QTest.mouseClick(d.add_button,Qt.LeftButton);_qt.processEvents();assert len(d.workbench.records)==1
 d.manual_tabs.setCurrentIndex(1);_qt.processEvents();d.table.setCurrentCell(0,0);d.destination_block.setText('بلوک۱');d.destination_floor.setText('دوم');d.destination_location.setText('آکس۱');d.formula_reason.setText('انتقال پیش‌نویس');d.formula_scroll.ensureWidgetVisible(d.formula_move_button);_qt.processEvents();QTest.mouseClick(d.formula_move_button,Qt.LeftButton);_qt.processEvents();assert d.workbench.records[0].floor_id=='دوم',d.status.text()
 d.manual_tabs.setCurrentIndex(0);_qt.processEvents();QTest.mouseClick(d.save_button,Qt.LeftButton);_qt.processEvents();assert s.open_project('P')['takeoffs'][0]['system']=='دوم';assert s.open_project('P')['boq'][0]['quantity']==0.75
 d.close();d.deleteLater();_qt.processEvents();s.store.close()
