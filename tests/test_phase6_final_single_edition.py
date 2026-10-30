"""Active desktop must not inherit historical edition restrictions."""
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('legacy', ['light', 'standard', 'pro', 'enterprise'])
def test_project_assistant_ignores_legacy_environment_without_bypassing_missing_model(tmp_path, monkeypatch, legacy):
    from core.ai.project_assistant import ProjectAssistant
    monkeypatch.setenv('STRUCTURALPRO_EDITION', legacy)
    monkeypatch.setenv('STRUCTURALPRO_AI_MODEL_DIR', str(tmp_path))
    assistant=ProjectAssistant()
    assert assistant.engine.edition == 'unified'
    assert not assistant.engine.has_llm_model
    result=assistant.review({'id':'P','name':'explicit fixture','takeoffs':[],'boq':[]})
    assert result['source']=='local-rule-engine'
    assert not result['quantity_authority']
    assert result['requires_user_confirmation']


def test_actual_desktop_legacy_environment_cannot_hide_ai_controls(tmp_path):
    root=Path(__file__).resolve().parents[1]
    code=r'''
import sys
from pathlib import Path
Path.home=classmethod(lambda cls:Path(sys.argv[1]))
from PySide6.QtWidgets import QApplication,QMainWindow,QPushButton,QLabel,QTextEdit,QLineEdit,QStackedWidget
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
service=StructuralProApp(Path(sys.argv[1])/'.structuralpro')
service.create_project('Explicit single edition fixture','P')
before=service.store.current_digest('P');service.store.close()
from app.main import main
real_exec=QApplication.exec

def inspect(app):
 w=next(x for x in app.topLevelWidgets() if isinstance(x,QMainWindow))
 assert w.findChild(QLabel,'EditionBadge').text()=='نسخه کامل'
 run=w.findChild(QPushButton,'LocalAIRun')
 assert run is not None and run.isEnabled()
 assert any(b.text()=='تحلیل تصویر' and b.isEnabled() for b in w.findChildren(QPushButton))
 stack=w.findChild(QStackedWidget)
 page=next(stack.widget(i) for i in range(stack.count()) if stack.widget(i).findChild(QPushButton,'LocalAIRun'))
 stack.setCurrentWidget(page);app.processEvents()
 page.findChild(QLineEdit,'LocalAIQuestion').setText('Explain missing evidence without inventing values')
 QTest.mouseClick(run,Qt.MouseButton.LeftButton);app.processEvents()
 assert 'موجود نیست' in page.findChildren(QTextEdit)[0].toPlainText()
 check=StructuralProApp(Path(sys.argv[1])/'.structuralpro')
 assert check.store.current_digest('P')==before and check.open_project('P')['boq']==[]
 check.store.close()
 QTimer.singleShot(0,w.close)
 return real_exec()
QApplication.exec=inspect
raise SystemExit(main())
'''
    env={**os.environ,'STRUCTURALPRO_EDITION':'light','STRUCTURALPRO_SMOKE':'0',
         'QT_QPA_PLATFORM':os.getenv('QT_QPA_PLATFORM','offscreen'),
         'STRUCTURALPRO_AI_MODEL_DIR':str(tmp_path/'missing-models'),
         'STRUCTURALPRO_AI_RUNTIME_DIR':str(tmp_path/'missing-runtime')}
    r=subprocess.run([sys.executable,'-c',code,str(tmp_path)],cwd=root,env=env,capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stdout+r.stderr
