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
  question=page.findChild(QtWidgets.QLineEdit,'LocalAIQuestion')
  run=page.findChild(QtWidgets.QPushButton,'LocalAIRun')
  discard=page.findChild(QtWidgets.QPushButton,'LocalAIDiscard')
  assert question is not None and run is not None and discard is not None
  if edition=='light':
   assert not run.isEnabled()
  else:
   question.setText('State why verified source documents and human review are necessary. No numerical examples.')
   QTest.mouseClick(run,Qt.LeftButton);app.processEvents()
   text=page.findChildren(QtWidgets.QTextEdit)[0].toPlainText()
   if os.environ.get('STRUCTURALPRO_REAL_AI_PROBE'):
    assert 'local-gguf' in text
    receipt['model_output']=text
   else: assert 'موجود نیست' in text
   if os.environ.get('STRUCTURALPRO_REAL_AI_PROBE') and edition in ('pro','enterprise'):
    path=page.findChildren(QtWidgets.QLineEdit)[-1]
    path.setText(os.environ['STRUCTURALPRO_REAL_AI_IMAGE'])
    image_run=next(b for b in page.findChildren(QtWidgets.QPushButton) if b.text()=='تحلیل تصویر')
    QTest.mouseClick(image_run,Qt.LeftButton);app.processEvents()
    image_text=page.findChildren(QtWidgets.QTextEdit)[0].toPlainText()
    assert 'local-gguf-vision' in image_text
    receipt['vision_output']=image_text
   QTest.mouseClick(discard,Qt.LeftButton);app.processEvents()
   assert 'رد شد' in page.findChildren(QtWidgets.QTextEdit)[0].toPlainText()
  w.grab().save(str(root/'ai-native.png'))
  check=StructuralProApp(root/'.structuralpro');assert check.store.current_digest('P')==before and check.open_project('P')['boq']==[];check.store.close()
  receipt.update(status='PASS',edition=edition,qt_click=edition!='light',disabled_checked=edition=='light',boq_unchanged=True)
 except Exception:receipt.update(status='FAIL',traceback=traceback.format_exc())
 finally:
  (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
  pass # Product smoke path owns window deletion and QApplication shutdown.
original_shot=QTimer.singleShot
def schedule(interval, callback, *args):
 if getattr(callback, '__name__', '')=='close_smoke_window':
  def drive_then_close():
   drive();callback()
  return original_shot(300,drive_then_close)
 return original_shot(interval,callback,*args)
QTimer.singleShot=schedule
os.environ['STRUCTURALPRO_SMOKE']='1'
from app.main import main
code=main()
print(json.dumps(receipt,ensure_ascii=False));sys.exit(0 if receipt.get('status')=='PASS' and code==0 else 1)
