"""Qt-free click-level smoke test of bored pile draft UI; real Qt is pending."""
import importlib
import sys
from types import ModuleType
import pytest

from test_bored_pile_draft_controller import SqliteService, _input, _owner, _json, domain_stubs


class Signal:
    def __init__(self):
        self.callback = None
    def connect(self, callback):
        self.callback = callback
    def emit(self):
        assert self.callback is not None, "دکمه باید متصل باشد"
        self.callback()


class Widget:
    def __init__(self, *args, **kwargs):
        self.value = str(args[0]) if args and isinstance(args[0],str) else ''
        self.items = []
        self.index = 0
        self.clicked = Signal()
        self.rows = []
    def setObjectName(self,*args):pass
    def setWindowTitle(self,*args):pass
    def setLayoutDirection(self,*args):pass
    def resize(self,*args):pass
    def addWidget(self,*args):pass
    def addLayout(self,*args):pass
    def addRow(self,*args):pass
    def addTab(self,*args):pass
    def setWidgetResizable(self,*args):pass
    def setWidget(self,*args):pass
    def setMaximumHeight(self,*args):pass
    def setPlaceholderText(self,*args):pass
    def setWordWrap(self,*args):pass
    def setReadOnly(self,*args):pass
    def setEditTriggers(self,*args):pass
    def setItemDelegate(self,delegate):self.delegate=delegate
    def setHorizontalHeaderLabels(self,*args):pass
    def resizeColumnsToContents(self):pass
    def setCurrentIndex(self,index):self.index=index
    def setText(self,value):self.value=str(value)
    def text(self):return self.value
    def setPlainText(self,value):self.value=str(value)
    def toPlainText(self):return self.value
    def clear(self):self.value=''
    def addItem(self,label,value):self.items.append((label,value))
    def currentData(self):return self.items[self.index][1] if self.items else None
    def findData(self,value):return next((i for i,item in enumerate(self.items) if item[1]==value),-1)
    def setRowCount(self,count):self.rows=[{} for _ in range(count)]
    def setItem(self,row,col,value):self.rows[row][col]=value
    def reject(self):self.rejected=True
    def exec(self):return 0
    def click(self):self.clicked.emit()


class Dialog(Widget):
    last = None
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        Dialog.last=self


class FileDialog:
    next_path = ''
    @staticmethod
    def getOpenFileName(*args):
        return FileDialog.next_path,''


class MessageBox:
    errors = []
    @staticmethod
    def warning(*args):
        MessageBox.errors.append(args[-1])


@pytest.fixture
def qt_stub(monkeypatch):
    module=ModuleType('PySide6')
    core=ModuleType('PySide6.QtCore')
    widgets=ModuleType('PySide6.QtWidgets')
    class LayoutDirection:RightToLeft=1
    class Qt:pass
    Qt.LayoutDirection=LayoutDirection
    core.Qt=Qt
    class Table(Widget):
        class EditTrigger:NoEditTriggers=0
    for name in (
        'QComboBox','QFileDialog','QFormLayout','QHBoxLayout','QLabel','QLineEdit',
        'QMessageBox','QPlainTextEdit','QPushButton','QScrollArea','QTableWidget',
        'QTableWidgetItem','QTabWidget','QVBoxLayout','QWidget','QDialog'
    ):
        item={'QFileDialog':FileDialog,'QMessageBox':MessageBox,
              'QDialog':Dialog,'QTableWidget':Table}.get(name,Widget)
        setattr(widgets,name,item)
    monkeypatch.setitem(sys.modules,'PySide6',module)
    monkeypatch.setitem(sys.modules,'PySide6.QtCore',core)
    monkeypatch.setitem(sys.modules,'PySide6.QtWidgets',widgets)
    struct=ModuleType('core.takeoff.reviewed_structural')
    struct._key=lambda kind,floor,member:kind+'|'+floor+'|'+member
    monkeypatch.setitem(sys.modules,'core.takeoff.reviewed_structural',struct)
    delegate_module=ModuleType('app.shear_wall_detail_editor')
    delegate_module.ExactCellDelegate=Widget
    monkeypatch.setitem(sys.modules,'app.shear_wall_detail_editor',delegate_module)
    sys.modules.pop('app.bored_pile_detail_editor',None)
    try:
        yield
    finally:
        sys.modules.pop('app.bored_pile_detail_editor',None)


def test_draft_buttons_work_and_stay_nonfinancial(tmp_path,qt_stub):
    MessageBox.errors.clear()
    service=SqliteService(tmp_path/'db.sqlite')
    screen=importlib.import_module('app.bored_pile_detail_editor')
    screen.open_bored_pile_editor(service,project_id='P',floor_id='FND',group_id='PG1')
    ctrl=Dialog.last.pile_controls
    assert ctrl['controller'].revision==0
    ctrl['new'].click()
    data=_input()
    path=_json(tmp_path/'input.json',data)
    ctrl['source_mode'].setCurrentIndex(ctrl['source_mode'].findData('manual'))
    ctrl['source_id'].setText('S1')
    ctrl['approved_by'].setText('Author')
    ctrl['measurement_ref'].setText('synthetic-doc')
    FileDialog.next_path=str(path)
    ctrl['input'].click()
    assert ctrl['controller'].data['pile_detail']['input']['piles'][0]['id']=='BP1'
    ctrl['reviewer'].setText('IndependentPreview')
    ctrl['ownership_claim'].setText('claim')
    owner_path=_json(tmp_path/'ownership.json',_owner(data))
    ctrl['ownership_reference'].setText('source-backed')
    FileDialog.next_path=str(owner_path)
    ctrl['owner'].click()
    assert ctrl['reviewer'].text()=='IndependentPreview'
    ctrl['preview'].click()
    assert 'commit_allowed' in ctrl['report'].toPlainText()
    ctrl['save'].click()
    assert ctrl['controller'].revision==1 and not ctrl['controller'].dirty
    ctrl['load'].click()
    assert ctrl['controller'].revision==1
    ctrl['history_refresh'].click()
    ctrl['close'].click()
    assert Dialog.last.rejected and not MessageBox.errors
    assert service.open_project('P')['boq']==[]
    assert not any(name in ctrl for name in ('commit','financial_commit','pay','approve_boq'))
    service.close()


def test_parent_menu_has_guarded_pile_launcher():
    from pathlib import Path
    import ast
    path=Path(__file__).resolve().parents[1]/'app/reviewed_structural_manual_editor.py'
    code=path.read_text(encoding='utf-8')
    ast.parse(code)
    assert "pile_specialist.clicked.connect(launch_bored_pile)" in code
    assert "if k!='bored_pile'" in code
    assert "open_bored_pile_editor(service,parent=dialog" in code
    assert "pile_specialist.setEnabled(kinds.currentData()=='bored_pile')" in code
