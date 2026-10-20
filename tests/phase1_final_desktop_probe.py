"""Real main-window QTest probe, isolated HOME and event loop; source acceptance only."""
import json,sys,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
output=Path(sys.argv[1]).resolve();output.mkdir(parents=True,exist_ok=True)
Path.home=classmethod(lambda cls:output)
from PySide6.QtCore import Qt,QTimer,QEvent,QCoreApplication,QDate,QCalendar,QLocale
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMainWindow,QTabBar,QPushButton,QStackedWidget,QLineEdit,QFrame,QDockWidget,QLabel
from core.platform.application import StructuralProApp
from app.main import main
native_exec=QApplication.exec

def exercise(app):
 w=next(x for x in app.topLevelWidgets() if isinstance(x,QMainWindow))
 assert w.layoutDirection()==Qt.RightToLeft
 tabs=w.findChild(QTabBar,'MainNavigationTabs');pages=w.findChild(QStackedWidget)
 assert tabs and tabs.count()>5
 brand=w.findChild(QLabel,'BrandTitle');app.processEvents()
 background=brand.grab().toImage().pixelColor(0,0)
 assert background.lightness()<100,'Header brand foreground must not sit on inherited near-white background'
 for width,height in [(1180,760),(1560,960)]:
  w.resize(width,height);app.processEvents();assert w.grab().save(str(output/f'main-{width}.png'))
 date=w.findChild(QPushButton,'SystemPersianDate');loc=QLocale(QLocale.Persian,QLocale.Iran)
 assert date and str(QCalendar(QCalendar.Jalali).partsFromDate(QDate.currentDate()).year) .translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹')) in date.text()
 index=next(i for i in range(tabs.count()) if 'متره سریع' in tabs.tabText(i))
 QTest.mouseClick(tabs,Qt.LeftButton,pos=tabs.tabRect(index).center());app.processEvents()
 page=pages.currentWidget();assert w.findChild(QFrame,'CommandRibbon')
 service=StructuralProApp(output/'.structuralpro');service.create_project('مصنوعی؛ آزمون رابط نهایی','FINAL-UI')
 page.findChildren(QLineEdit)[0].setText('FINAL-UI')
 errors=[];seen=[]
 def child():
  d=app.activeModalWidget()
  try:
   from app.manual_takeoff import ManualTakeoffDialog
   assert isinstance(d,ManualTakeoffDialog) and d.layoutDirection()==Qt.RightToLeft
   assert d.grab().save(str(output/'manual-menu.png'));seen.append('manual_from_main_menu')
  except Exception:errors.append(traceback.format_exc())
  finally:
   if d:d.reject()
 QTimer.singleShot(60,child)
 b=next(b for b in page.findChildren(QPushButton) if 'متره دستی حرفه‌ای' in b.text())
 QTest.mouseClick(b,Qt.LeftButton);assert seen and not errors,errors
 assert not service.open_project('FINAL-UI')['boq'];service.store.close()
 (output/'ui-result.json').write_text(json.dumps({'platform':sys.platform,'manual_menu':seen,'tabs':[tabs.tabText(i) for i in range(tabs.count())],'dock_widgets':len(w.findChildren(QDockWidget)),'sizes':[[1180,760],[1560,960]],'windows_acceptance':False},ensure_ascii=False,indent=2))


def loop(app):
 result={'code':1}
 def run():
  try:exercise(app);result['code']=0
  except Exception:traceback.print_exc()
  finally:
   for w in app.topLevelWidgets():w.close()
   QTimer.singleShot(20,app.quit)
 QTimer.singleShot(50,run);native_exec();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents();return result['code']
QApplication.exec=loop
raise SystemExit(main())
