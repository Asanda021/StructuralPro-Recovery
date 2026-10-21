from decimal import Decimal
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from PySide6.QtCore import Qt
from app.manual_formula_controls import VisibleRowsTable

def test_native_table_exact_numeric_natural_stable_and_selection():
 global _qt
 _qt=QApplication.instance() or QApplication([]);t=VisibleRowsTable(6,4);t.show()
 values=['10','2','123456789012345678901234567890.2','123456789012345678901234567890.1','-2','2']
 for i,value in enumerate(values):
  t.setItem(i,0,QTableWidgetItem('A'+str(i)));t.setItem(i,1,QTableWidgetItem(value));t.setItem(i,2,QTableWidgetItem('طبقه'+str([10,2,3,4,5,6][i])));t.setItem(i,3,QTableWidgetItem(str([10,2,3,4,5,6][i])))
 assert callable(getattr(t,'set_sort_kinds',None)), 'مرتب‌سازی جدول هنوز متنی است'
 t.set_sort_kinds({0:'natural',1:'number',2:'natural',3:'number'});t.setSortingEnabled(True);t.setCurrentCell(0,0);selected=t.item(0,0).text();t.sortItems(1,Qt.AscendingOrder)
 assert [t.item(i,1).text() for i in range(6)]==['-2','2','2','10',values[3],values[2]]
 assert t.item(1,0).text()=='A1' and t.item(2,0).text()=='A5';assert t.item(t.currentRow(),0).text()==selected
 t.sortItems(2,Qt.AscendingOrder);assert t.item(0,2).text()=='طبقه2' and t.item(5,2).text()=='طبقه10'
 t.close();t.deleteLater();_qt.processEvents()

def test_dates_versions_descending_equal_order_and_exact_decimals():
 global _qt
 _qt=QApplication.instance() or QApplication([]);t=VisibleRowsTable(3,3);t.set_sort_kinds({0:'natural',1:'number',2:'date'})
 for r,(identity,version,date) in enumerate([('عضو2','2','2026-10-14T00:30:00+03:30'),('عضو10','10','2026-10-13T23:00:00+00:00'),('عضو3','2','2026-10-13T20:00:00+00:00')]):
  for c,v in enumerate([identity,version,date]):t.setItem(r,c,QTableWidgetItem(v))
 t.setSortingEnabled(True);t.sortItems(1,Qt.DescendingOrder);assert [t.item(i,0).text() for i in range(3)]==['عضو10','عضو2','عضو3']
 t.sortItems(2,Qt.AscendingOrder);assert [t.item(i,0).text() for i in range(3)]==['عضو3','عضو2','عضو10'];t.close();t.deleteLater();_qt.processEvents()
