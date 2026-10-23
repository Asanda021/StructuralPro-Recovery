from pathlib import Path
import sys,os,json,traceback
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
Path.home=classmethod(lambda cls:root)
from core.platform.application import StructuralProApp
service=StructuralProApp(root/'.structuralpro');service.create_project('نمونه صریح آزمون AI','P');before=service.store.current_digest('P');service.store.close()
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
Original=QtWidgets.QApplication
receipt={}
def drive():
 try:
  app=Original.instance();w=next(x for x in app.topLevelWidgets() if isinstance(x,QtWidgets.QMainWindow))
  selected=None
  for stack in w.findChildren(QtWidgets.QStackedWidget):
   for i in range(stack.count()):
    page=stack.widget(i)
    buttons=[b for b in page.findChildren(QtWidgets.QPushButton) if b.text()=='🤖 بازبینی پروژه']
    if buttons:
     selected=(stack,i,page,buttons[0]);break
   if selected:break
  assert selected
  stack,i,page,button=selected;stack.setCurrentIndex(i);app.processEvents()
  edition=os.environ['STRUCTURALPRO_EDITION']
  if edition=='light':assert not button.isEnabled()
  else:
   page.findChildren(QtWidgets.QLineEdit)[0].setText('P')
   QTest.mouseClick(button,Qt.LeftButton);app.processEvents()
   output=page.findChildren(QtWidgets.QTextEdit)[0].toPlainText();assert 'متره' in output
   receipt['output']=output
  w.grab().save(str(root/'ai-native.png'))
  check=StructuralProApp(root/'.structuralpro');assert check.store.current_digest('P')==before and check.open_project('P')['boq']==[];check.store.close()
  receipt.update(status='PASS',edition=edition,qt_click=True,boq_unchanged=True)
 except Exception:receipt.update(status='FAIL',traceback=traceback.format_exc())
 finally:
  (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
  for widget in Original.instance().topLevelWidgets():widget.close()
  Original.instance().quit()
class ProbeApplication(Original):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);QTimer.singleShot(300,drive)
QtWidgets.QApplication=ProbeApplication
from app.main import main
code=main()
print(json.dumps(receipt,ensure_ascii=False));sys.exit(0 if receipt.get('status')=='PASS' and code==0 else 1)
