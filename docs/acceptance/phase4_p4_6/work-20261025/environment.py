import os,sys,json,platform,sqlite3,subprocess,shutil,importlib.metadata as md
from pathlib import Path
out=Path(__file__).parent
packages=['PySide6','ifcopenshell','PyMuPDF','arabic-reshaper','python-bidi','reportlab','openpyxl','python-docx','ezdxf','pytest']
r={'python':sys.version,'executable':sys.executable,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'cpu_count':os.cpu_count(),'cpu':Path('/proc/cpuinfo').read_text().split('model name')[1].splitlines()[0],'memory':Path('/proc/meminfo').read_text(),'disk':list(shutil.disk_usage('.')),'packages':{p:md.version(p) for p in packages},'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()}
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
app=QApplication([]);button=QPushButton('آزمون واقعی');clicks=[];button.clicked.connect(lambda:clicks.append(True));button.show();QTest.mouseClick(button,Qt.MouseButton.LeftButton);QTest.qWait(10);assert clicks==[True];r['qt']={'platform':app.platformName(),'QTest_click':True};button.close()
(out/'environment.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False))
