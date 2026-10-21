"""Real offscreen Qt clicks from an empty roof form; explicit synthetic input."""
from copy import deepcopy
from pathlib import Path
import pytest
from test_waffle_specialist_work import sample,KINDS
from core.platform.application import StructuralProApp

@pytest.mark.parametrize('kind',KINDS)
def test_empty_form_complete_click_journey(tmp_path,kind,monkeypatch):
 from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog,QComboBox,QTableWidgetItem,QScrollArea,QTabWidget
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.roof_detail_editor import open_roof_editor,REGIONS,DEDUCTIONS,WAFFLE_PIECES,STEEL,FACES,PROPS,LAYOUT,RIB_LAYOUT
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('نمونه صریح مصنوعی','P');data=sample(kind);errors=[];warnings=[];clicks=[]
 monkeypatch.setattr(QMessageBox,'warning',lambda parent,title,text,*_:warnings.append(str(text)))
 monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.Yes)
 fmt=[None]
 monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(tmp_path/('clicked-'+kind+'.'+fmt[0])),''))
 def click(b,name):
  tabs=b.window().findChild(QTabWidget)
  if tabs:
   for i in range(tabs.count()):
    if tabs.widget(i).isAncestorOf(b):tabs.setCurrentIndex(i);break
   _qt.processEvents()
  w=b
  while w:
   parent=w.parentWidget()
   if isinstance(parent,QTabWidget):parent.setCurrentWidget(w)
   if isinstance(w,QScrollArea):w.ensureWidgetVisible(b)
   w=parent
  QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents();clicks.append(name)
 def select(t,row):
  t.scrollToItem(t.item(row,0));QTest.mouseClick(t.viewport(),Qt.LeftButton,pos=t.visualItemRect(t.item(row,0)).center());_qt.processEvents()
 def fill(c,key,cols,records):
  t=c[key]
  if not t.isEnabled():
   assert not records
   return
  click(c[key+'_add'],key+'_add');select(t,t.rowCount()-1);click(c[key+'_remove'],key+'_remove');assert t.rowCount()==0,key
  for record in records:
   click(c[key+'_add'],key+'_add');row=t.rowCount()-1
   for col,(k,_) in enumerate(cols):
    w=t.cellWidget(row,col)
    if w:w.setCurrentIndex(w.findData(record.get(k)))
    else:t.setItem(row,col,QTableWidgetItem(str(record.get(k,''))))
 def run():
  dlg=_qt.activeModalWidget();c=dlg.roof_controls
  try:
   c['id'].setText('S1');click(c['new'],'new');g=data['roof_detail']['geometry']
   for k in ('unit','shape','repeat_scope','action','joist_axis','joist_supply_scope','rib_axis'):
    if k in g:c[k].setCurrentIndex(c[k].findData(g[k]))
   for k in ('length','width','depth','count','topping_thickness','joist_count','joist_spacing'):
    if k in g:c[k].setText(g[k])
   for key,value in [('building','B1'),('source',data['source']['source_id']),('plan',data['source']['plan_ref']),('detail',data['source']['detail_ref']),('geometry_ref',g['source_ref']),('geometry_approver',g['approved_by']),('deductions_ref','عدم بازشو مصنوعی'),('pieces_ref','چیدمان مصنوعی')]:c[key].setText(value)
   for key,cols in [('regions',REGIONS),('deductions',DEDUCTIONS),('pieces',WAFFLE_PIECES),('joist_layout',LAYOUT),('rib_layout',RIB_LAYOUT)]:fill(c,key,cols,data['roof_detail'][key])
   for group,part in data['roof_detail']['rebars'].items():
    c['bar_group'].setCurrentIndex(c['bar_group'].findData(group));c['bar_status'].setCurrentIndex(c['bar_status'].findData(part['status']))
    for k,v in [('bar_approver',part['approved_by']),('bar_ref',part['source_ref']),('bar_reason',part.get('reason',''))]:c[k].setText(v)
    fill(c,'bars',STEEL,part.get('series',[]))
    if part.get('series'):
     select(c['bars'],0)
     def nested():
      child=_qt.activeModalWidget();cc=child.cut_controls
      try:
       click(cc['add'],'cut_add');select(cc['grid'],0);click(cc['remove'],'cut_remove');click(cc['add'],'cut_add')
       for col,value in enumerate(['straight','4','دیتایل برش مصنوعی']):cc['grid'].setItem(0,col,QTableWidgetItem(value))
       click(cc['save'],'cut_save')
      except Exception as exc:errors.append(repr(exc));child.reject()
     QTimer.singleShot(20,nested);click(c['cut'],'cut')
     select(c['bars'],0)
     QTimer.singleShot(20,lambda:click(_qt.activeModalWidget().cut_controls['cancel'],'cut_cancel'));click(c['cut'],'cut')
    click(c['store_bar'],'store_bar')
   for key,cols,listkey in [('formwork',FACES,'faces'),('shoring',PROPS,'props')]:
    p=data['roof_detail'][key];c[key+'_status'].setCurrentIndex(c[key+'_status'].findData(p['status']))
    for suffix,field in [('approver','approved_by'),('ref','source_ref'),('reason','reason')]:c[key+'_'+suffix].setText(p.get(field,''))
    fill(c,key,cols,p.get(listkey,[]))
   click(c['preview'],'preview');assert 'محاسبه معتبر' in c['message'].text(),(c['message'].text(),warnings)
   click(c['save'],'save');assert a.get_aec_system('P',kind,'L1','S1')['revision']==1,warnings
   click(c['load'],'load');c['plan'].setText('ویرایش مستند پلان مصنوعی');click(c['save'],'edit_save');assert a.get_aec_system('P',kind,'L1','S1')['revision']==2,warnings
   click(c['load'],'load');c['reviewer'].setText('بازبین مستقل مصنوعی');c['note'].setText('کنترل واقعی نمونه مصنوعی');click(c['review'],'review');assert a.get_aec_system('P',kind,'L1','S1')['revision']==3,warnings
   click(c['commit'],'commit');assert a.get_aec_system('P',kind,'L1','S1')['status']=='committed',warnings
   before=deepcopy(a.open_project('P'));c['count'].setText('2');c['creator'].setText('سازنده مصنوعی');c['reason'].setText('اصلاح دیتایل مصنوعی');path=tmp_path/'revision.txt';path.write_text('explicit synthetic revised detail');c['evidence_path'].setText(str(path));c['evidence_ref'].setText('مرجع جدید مصنوعی')
   click(c['create_amendment'],'create_amendment');assert c['amend_id'].text(),warnings
   click(c['review_amendment'],'review_amendment');click(c['apply_amendment'],'apply_amendment');assert a.get_aec_system('P',kind,'L1','S1')['revision']==4,warnings
   assert a.open_project('P')['takeoffs']==before['takeoffs'] and a.open_project('P')['boq']!=before['boq']
   for ext in ('pdf','xlsx','docx','csv'):
    fmt[0]=ext;click(c[ext],ext);assert (tmp_path/('clicked-'+kind+'.'+ext)).is_file(),warnings
   c['new_id'].setText('S2');c['new_source'].setText('COPY-'+kind);click(c['copy'],'copy');assert a.get_aec_system('P',kind,'L1','S2'),warnings
   click(c['delete'],'delete');assert a.get_aec_system('P',kind,'L1','S2') is None,warnings
   c['id'].setText('S1');click(c['load'],'load');click(c['delete'],'reject_delete');assert any('قطعی' in x for x in warnings);warnings.clear()
   assert len(clicks)>50;assert not warnings,warnings
  except Exception as exc:errors.append(repr(exc))
  finally:dlg.reject()
 QTimer.singleShot(50,run);open_roof_editor(a,project_id='P',floor_id='L1',kind=kind)
 a.store.close();assert not errors,errors


@pytest.mark.parametrize('kind',KINDS)
def test_existing_aec_form_launches_specialist(tmp_path,monkeypatch,kind):
 from PySide6.QtWidgets import QApplication,QComboBox
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');errors=[]
 def run():
  parent=_qt.activeModalWidget()
  try:
   combo=next(w for w in parent.findChildren(QComboBox) if w.findData(kind)>=0);combo.setCurrentIndex(combo.findData(kind))
   def child():
    d=_qt.activeModalWidget()
    try:assert d.objectName()=='RoofDetailEditor' and hasattr(d,'roof_controls')
    except Exception as exc:errors.append(repr(exc))
    finally:d.reject()
   QTimer.singleShot(20,child);QTest.mouseClick(parent.roof_button,Qt.LeftButton)
  except Exception as exc:errors.append(repr(exc))
  finally:parent.reject()
 QTimer.singleShot(30,run);open_reviewed_aec_editor(a,project_id='P',floor_id='L1');a.store.close();assert not errors,errors
