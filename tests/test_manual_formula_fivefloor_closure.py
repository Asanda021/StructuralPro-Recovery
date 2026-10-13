"""Explicit synthetic formula fixtures; not real plans/design approval."""
import json
from decimal import Decimal
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog
from core.platform.application import StructuralProApp
from app.manual_takeoff import ManualTakeoffDialog

CASES=[
 ('بتن','column','m3','طول*عرض*ارتفاع',{'طول':'4','عرض':'0.5','ارتفاع':'3'},'6'),
 ('میلگرد','beam_reinforcement','kg','تعداد*طول*وزن',{'تعداد':'2','طول':'3','وزن':'0.888'},'5.328'),
 ('قالب','beam_concrete_formwork','m2','2*(عرض+ارتفاع)*طول',{'عرض':'0.5','ارتفاع':'3','طول':'4'},'28'),
 ('دیوار','block_wall','m2','طول*ارتفاع-بازشو',{'طول':'10','ارتفاع':'3','بازشو':'2'},'28'),
 ('گچ‌وخاک','plaster_finish','m2','طول*ارتفاع-بازشو',{'طول':'10','ارتفاع':'3','بازشو':'2'},'28'),
 ('سفیدکاری','plaster_finish','m2','طول*ارتفاع-بازشو',{'طول':'10','ارتفاع':'3','بازشو':'2'},'28'),
 ('کف‌سازی','floor_finish','m3','طول*عرض*ضخامت',{'طول':'5','عرض':'4','ضخامت':'0.1'},'2'),
 ('کاشی','ceramic_finish','m2','طول*ارتفاع',{'طول':'5','ارتفاع':'2'},'10'),
 ('سرامیک','ceramic_finish','m2','طول*عرض',{'طول':'5','عرض':'4'},'20'),
 ('رنگ','paint_finish','m2','طول*ارتفاع-بازشو',{'طول':'10','ارتفاع':'3','بازشو':'2'},'28'),
 ('عایق','waterproofing','m2','طول*عرض',{'طول':'5','عرض':'4'},'20'),
 ('سقف کاذب','suspended_ceiling','m2','طول*عرض',{'طول':'5','عرض':'4'},'20'),
 ('لوله‌کشی','plumbing','m','تعداد*طول',{'تعداد':'3','طول':'4'},'12'),
 ('برق‌کشی','electrical_power','m','تعداد*طول',{'تعداد':'4','طول':'5'},'20'),
]

def click(button,qt):QTest.mouseClick(button,Qt.LeftButton);qt.processEvents()

def select_key(d,key,qt):
 row=next(i for i in range(d.formula_table.rowCount()) if d.formula_table.item(i,0).text()==key)
 d.formula_table.scrollToItem(d.formula_table.item(row,0));qt.processEvents()
 QTest.mouseClick(d.formula_table.viewport(),Qt.LeftButton,pos=d.formula_table.visualItemRect(d.formula_table.item(row,0)).center());qt.processEvents()

def test_real_qt_fourteen_operations_five_floors_and_all_reports(tmp_path,monkeypatch):
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path/'db');s.create_project('ساختمان پنج‌طبقه کاملاً مصنوعی','P');d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 for i,(label,family,unit,expression,variables,expected) in enumerate(CASES):
  d.formula_id.setText('A'+str(i));d._formula_revision=0;d._formula_selected=None;d.formula_source.setText('synthetic:fivefloor:A'+str(i));d.formula_member.setText('عضو-'+label);d.floor_id.setText('طبقه۱');d.formula_family.setCurrentIndex(d.formula_family.findData(family));d.formula_unit.setCurrentIndex(d.formula_unit.findData(unit));d.formula_title.setText(label);d.formula_expression.setText(expression);d.formula_variables.setPlainText('\n'.join(k+'='+v for k,v in variables.items()));d.formula_basis.setText('مصنوعی؛ ابعاد متر، تعداد عدد، وزن واحد کیلوگرم بر متر؛ بدون پرت یا دیتایل حدسی');d.formula_reason.setText('ورود صریح مصنوعی')
  click(d.formula_save_button,_qt);row=s.load_manual_formulas('P')['A'+str(i)];assert Decimal(str(row['quantity']))==Decimal(expected)
 for floor in ['طبقه۲','طبقه۳','طبقه۴','طبقه۵']:
  d.formula_search.setText('طبقه۱');_qt.processEvents();d.formula_table.setFocus();QTest.keyClick(d.formula_table,Qt.Key_A,Qt.ControlModifier);_qt.processEvents()
  assert len(d.formula_table.selectionModel().selectedRows())==14
  d.formula_copy_floor.setText(floor);d.formula_reason.setText('تکرار صریح اعضای مستقل در طبقه جدید');click(d.formula_floor_copy_button,_qt)
 assert len(s.load_manual_formulas('P'))==70,d.status.text()
 d.formula_search.clear();_qt.processEvents()
 # A failed incomplete edit must preserve every row.
 select_key(d,'A0',_qt);click(d.formula_load_button,_qt);d.formula_variables.setPlainText('طول=4');d.formula_reason.setText('ورودی ناقص');before=s.load_manual_formulas('P');click(d.formula_save_button,_qt);assert s.load_manual_formulas('P')==before
 d.formula_reviewer.setText('مهندس مصنوعی');d.formula_review_note.setText('مرجع مستقل هر فرمول و واحد کنترل شد')
 for key in list(s.load_manual_formulas('P')):
  select_key(d,key,_qt);click(d.formula_review_button,_qt);assert s.load_manual_formulas('P')[key]['status']=='reviewed',d.status.text();select_key(d,key,_qt);click(d.formula_commit_button,_qt);assert s.load_manual_formulas('P')[key]['status']=='committed',d.status.text()
 project=s.open_project('P');assert len(project['takeoffs'])==len(project['boq'])==70;assert len({r['source_id'] for r in project['boq']})==70
 for label,family,unit,expression,variables,expected in CASES:
  matching=[r for r in project['boq'] if r['description']==label];assert len(matching)==5;assert sum(Decimal(str(r['quantity'])) for r in matching)==Decimal(expected)*5
 for fmt,button in [('xlsx',d.formula_xlsx_button),('pdf',d.formula_pdf_button)]:
  path=tmp_path/('fivefloor.'+fmt);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,p=path,**kw:(str(p),''));click(button,_qt);assert path.exists(),d.status.text()
 d.grab().save(str(tmp_path/'fivefloor.png'));(tmp_path/'scenario.json').write_text(json.dumps({'synthetic':True,'cases':CASES,'floors':5,'rows':70},ensure_ascii=False,indent=2))
 d.close();d.deleteLater();_qt.processEvents();s.store.close();s=StructuralProApp(tmp_path/'db');reg=s.load_manual_formulas('P');assert len(reg)==70 and all(r['status']=='committed' for r in reg.values());assert len(s.open_project('P')['boq'])==70;s.store.close()
