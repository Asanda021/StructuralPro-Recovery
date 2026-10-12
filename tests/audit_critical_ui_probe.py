"""Real source desktop interaction in a disposable HOME (not Windows acceptance)."""
import sys
from pathlib import Path
import json
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
home = Path(sys.argv[1]); home.mkdir(parents=True, exist_ok=True)
Path.home = classmethod(lambda cls: home)
from PySide6.QtWidgets import QApplication, QMainWindow, QTabBar, QStackedWidget, QLineEdit, QComboBox, QPushButton, QTextEdit, QFileDialog
from app.main import main
from core.platform.application import StructuralProApp
from PySide6.QtCore import QTimer


def exercise(app):
    print("UI exercise start",flush=True)
    window = next(w for w in app.topLevelWidgets() if isinstance(w, QMainWindow))
    tabs = window.findChild(QTabBar, 'MainNavigationTabs')
    pages = window.findChild(QStackedWidget)
    index = next(i for i in range(tabs.count()) if 'متره سریع' in tabs.tabText(i))
    tabs.setCurrentIndex(index);
    page = pages.currentWidget()
    service = StructuralProApp(home / '.structuralpro')
    service.create_project('آزمون فرمان واقعی', 'UI')
    lines = page.findChildren(QLineEdit)
    lines[0].setText('UI'); lines[1].setText('2'); lines[2].setText('1'); lines[3].setText('1')
    output = page.findChild(QTextEdit)
    def persisted(): return service.open_project('UI')['takeoffs']
    button = next(b for b in page.findChildren(QPushButton) if b.text() == 'محاسبه و ثبت')
    button.click();
    assert 'خطا' not in output.toPlainText(), output.toPlainText()
    assert len(persisted()) == 1
    quantity = persisted()[0]['quantities'][0]
    assert quantity['amount'] == 2 and quantity['unit'] == 'm2'
    assert persisted()[0]['source_id']
    from PySide6.QtWidgets import QFrame
    ribbon_layout = window.findChild(QFrame, 'CommandRibbon').layout()
    ribbon = next(ribbon_layout.itemAt(i).widget() for i in range(ribbon_layout.count())
                  if isinstance(ribbon_layout.itemAt(i).widget(), QPushButton)
                  and ribbon_layout.itemAt(i).widget().objectName() == 'RibbonPrimary')
    ribbon.click();
    assert len(persisted()) == 2
    lines[1].clear()
    button.click();
    assert 'خطا' in output.toPlainText()
    assert len(persisted()) == 2
    service.store.close()
    reopened = StructuralProApp(home / '.structuralpro')
    assert len(reopened.open_project('UI')['takeoffs']) == 2
    reopened.store.close()
    if len(sys.argv)>2 and sys.argv[2]=='members':
        service=StructuralProApp(home/'.structuralpro');service.create_project('اعضای مستقل','M')
        item=next(c for c in page.findChildren(QComboBox) if c.findText('slab')>=0 or c.findData('slab')>=0)
        from core.aec.disciplines import takeoff_domain
        discipline=next(c for c in page.findChildren(QComboBox) if c is not item)
        selection=next(i for i in range(discipline.count()) if discipline.itemData(i) and takeoff_domain(discipline.itemData(i))=='building')
        discipline.setCurrentIndex(selection)
        for index,(code,dimensions,expected,unit) in enumerate([
            ('slab',(10,4,1),40,'m2'),('wall',(10,1,3),30,'m2'),
            ('column',(.4,.5,3),.6,'m3'),('beam',(4,.3,.5),.6,'m3'),
            ('footing_concrete',(2,1,.4),.8,'m3')],1):
            chosen=item.findData(code) if item.findData(code)>=0 else item.findText(code)
            item.setCurrentIndex(chosen);lines[0].setText('M')
            for field,value in zip(lines[1:4],dimensions):field.setText(str(value))
            button.click()
            assert 'خطا' not in output.toPlainText(),output.toPlainText()
            rows=service.open_project('M')['takeoffs'];assert len(rows)==index
            assert rows[-1]['params']['discipline']==discipline.currentData()
            q=rows[-1]['quantities'][0];assert abs(q['amount']-expected)<1e-8 and q['unit']==unit
        service.store.close()
    print('Quick button/Ribbon/reopen complete',flush=True)
    if len(sys.argv)>2 and sys.argv[2]=='finance':
        service=StructuralProApp(home/'.structuralpro')
        service.create_project('مالی مستقل','F')
        def go(label):
            tabs.setCurrentIndex(next(i for i in range(tabs.count()) if label in tabs.tabText(i)))
            return pages.currentWidget()
        def entry(p,text):return next(x for x in p.findChildren(QLineEdit) if text in x.placeholderText())
        def click(p,text):next(x for x in p.findChildren(QPushButton) if x.text()==text).click();
        from openpyxl import Workbook
        book=Workbook();sheet=book.active
        sheet.append(['سال','رشته','فصل','شماره ردیف','شرح','واحد','بهای واحد'])
        sheet.append([1404,'ابنیه','01','A','سطح نمونه','m2',100]);sheet.append([1404,'ابنیه','01','B','سطح دوم','m2',20])
        price_path=home/'explicit-prices.xlsx';book.save(price_path)
        p=go('فهرست‌بها');entry(p,'سال').setText('1404')
        QFileDialog.getOpenFileName=lambda *a,**k:(str(price_path),'')
        click(p,'📥 ورود Excel / CSV / PDF')
        p=go('متره سریع');lines=p.findChildren(QLineEdit);lines[0].setText('F')
        for code,quantity in [('A',2),('B',3)]:
            lines[1].setText(str(quantity));lines[2].setText('1');lines[4].setText(code)
            click(p,'محاسبه و ثبت');assert 'خطا' not in p.findChild(QTextEdit).toPlainText()
        assert len(service.open_project('F')['takeoffs'])==2
        p=go('برآورد و صورت');entry(p,'شناسه پروژه').setText('F');entry(p,'ضرایب').setText('سربار=0.1,منطقه=0.05');click(p,'بازسازی برآورد')
        assert abs(service.open_project('F')['estimate']['cost']['grand_total']-300.3)<1e-8
        print('Estimate button complete',flush=True)
        p=go('گزارشات');entry(p,'شناسه پروژه').setText('F');p.findChild(QComboBox).setCurrentText('xlsx')
        QFileDialog.getSaveFileName=lambda *a,**k:(str(home/'financial.xlsx'),'')
        click(p,'ساخت گزارش');assert (home/'financial.xlsx').exists()
        assert abs(service.open_project('F')['estimate']['cost']['grand_total']-300.3)<1e-8
        print('Report button complete',flush=True)
        p=go('صورت‌وضعیت');entry(p,'شناسه پروژه').setText('F');entry(p,'شماره دوره').setText('1')
        current=entry(p,'کارکرد:');assert current.parent() is not None;current.setText('A=2,B=3')
        p.findChild(QLineEdit,'Statement_retention_rate').setText('0.1')
        print('Statement fields set',flush=True)
        click(p,'محاسبه دوره');preview=json.loads(p.findChild(QTextEdit).toPlainText())
        assert preview['gross_current']==260 and preview['retention']==26
        assert service.statement_periods('F')==[]
        print('Statement preview complete',flush=True)
        click(p,'ذخیره دوره');period=service.statement_periods('F')[0]
        assert period==preview and period['payable_current']==234
        service.store.close()
        reopened=StructuralProApp(home/'.structuralpro');assert reopened.statement_periods('F')[0]==preview;reopened.store.close()
    print("UI interactions complete",flush=True)
    return 0


native_exec = QApplication.exec
def run_event_loop(app):
    result=exercise(app)
    # Let the real Qt event loop process native ownership/deferred cleanup,
    # as the existing desktop smoke does; do not quit mid-signal callback.
    QTimer.singleShot(100, app.quit)
    native_exec()
    return result
QApplication.exec = run_event_loop
raise SystemExit(main())
