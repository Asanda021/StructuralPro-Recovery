from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
from app.manual_takeoff import ManualTakeoffDialog
from test_manual_formula_persistence import data

def test_dynamic_related_fields_subitems_and_native_location_commands(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول');d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 assert hasattr(d,'dynamic_parameters'),'فرم گروه‌های متره هنوز پویا نیست'
 d.formula_family.setCurrentIndex(d.formula_family.findData('beam_reinforcement'));assert 'unit_weight' in d.dynamic_parameters and 'thickness' not in d.dynamic_parameters
 d.formula_family.setCurrentIndex(d.formula_family.findData('paint_finish'));assert 'unit_weight' not in d.dynamic_parameters and 'length' in d.dynamic_parameters
 assert d.formula_subitem.count()>1
 d.table.setCurrentCell(0,0);d.destination_block.setText('بلوک۲');d.destination_floor.setText('طبقه۲');d.destination_location.setText('آکس۲');d.formula_reason.setText('انتقال مستند');d.formula_scroll.ensureWidgetVisible(d.formula_move_button);_qt.processEvents();QTest.mouseClick(d.formula_move_button,Qt.LeftButton);_qt.processEvents()
 assert s.load_manual_formulas('P')['A']['data']['floor']=='طبقه۲',d.status.text()
 assert d.table is d.formula_table;d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_dynamic_typing_and_edit_after_numeric_header_sort(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P')
 s.save_manual_formula('P','A2',data(member='C2',source_id='s2',expression='length',variables={'length':'2'}),expected_revision=0,reason='اول');s.save_manual_formula('P','A10',data(member='C10',source_id='s10',expression='length',variables={'length':'10'}),expected_revision=0,reason='اول')
 d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents();d.table.sortItems(4,Qt.AscendingOrder);assert d.table.item(0,0).text()=='A2'
 d.table.setCurrentCell(0,0);QTest.mouseClick(d.formula_load_button,Qt.LeftButton);_qt.processEvents();assert d.formula_id.text()=='A2'
 field=d.dynamic_parameters['length'];d.formula_scroll.ensureWidgetVisible(field);field.setFocus();field.selectAll();QTest.keyClicks(field,'3');_qt.processEvents();assert d.dynamic_parameters['length'] is field
 d.formula_reason.setText('تغییر پس از مرتب‌سازی');QTest.mouseClick(d.formula_save_button,Qt.LeftButton);_qt.processEvents();assert s.load_manual_formulas('P')['A2']['quantity']==3 and s.load_manual_formulas('P')['A10']['quantity']==10
 assert d.table.horizontalHeader().sortIndicatorSection()==4;d.grab().save(str(tmp_path/'final-form.png'));d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_all_85_families_dynamic_contract_renders_without_defaults(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 assert d.formula_family.count()==86
 for i in range(1,86):
  d.formula_family.setCurrentIndex(i);_qt.processEvents();assert d.formula_subitem.count()>1
  assert d.dynamic_group.text()
  assert all(not field.text() for field in d.dynamic_parameters.values())
  assert all(field.placeholderText() and field.toolTip() for field in d.dynamic_parameters.values())
 d.close();d.deleteLater();_qt.processEvents();s.store.close()
