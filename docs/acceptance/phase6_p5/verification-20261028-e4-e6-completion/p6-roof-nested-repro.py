import json,subprocess,sys
code='''import sys
sys.path.insert(0,"tests")
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QTimer
import test_phase2_pdf_roof_ui as m
qt=QApplication.instance() or QApplication([])
other=QDialog();other.setObjectName("UnexpectedNestedModal")
QTimer.singleShot(100,other.exec)
try:
 m.test_delayed_roof_modal_is_seen_even_if_construction_is_slow(qt)
except AssertionError:
 print("Expected explicit assertion; active modal:",qt.activeModalWidget(),flush=True)
 raise SystemExit(0 if qt.activeModalWidget() is None else 3)
raise SystemExit(2)
'''
try:
 p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=4)
 print(json.dumps({'timed_out':False,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}))
except subprocess.TimeoutExpired:
 print(json.dumps({'timed_out':True,'external_bound_seconds':4,'observation':'Fixture did not unwind its known roof modal after the helper deadline'}))
 raise SystemExit(124)
