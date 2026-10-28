from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
app=QApplication([])
observed=[]
def old_one_shot():
    box=app.activeModalWidget()
    observed.append(isinstance(box,QMessageBox))
def open_delayed():
    box=QMessageBox()
    box.setOption(QMessageBox.Option.DontUseNativeDialog)
    box.setObjectName('BoredPileErrorMessage')
    box.setStandardButtons(QMessageBox.Ok)
    QTimer.singleShot(150,lambda: QTest.mouseClick(box.button(QMessageBox.Ok),Qt.LeftButton))
    box.exec()
QTimer.singleShot(10,old_one_shot)
QTimer.singleShot(80,open_delayed)
QTimer.singleShot(350,app.quit)
app.exec()
print('old one-shot observed expected QMessageBox:',observed)
assert observed==[True], 'RED: one-shot expired before the real QMessageBox appeared'
