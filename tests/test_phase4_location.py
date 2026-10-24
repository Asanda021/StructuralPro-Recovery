from pathlib import Path
from core.platform.application import StructuralProApp

def test_existing_drawing_highlight_and_changed_source_fail_closed(tmp_path):
    assert hasattr(StructuralProApp,'activity_locations'),'existing drawing/member handoff absent'
    from PySide6.QtWidgets import QApplication,QPushButton
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from scripts.phase3_financial_probe import run
    from test_phase4_structure import cmd
    from app.project_controls_workspace import ProjectControlsWorkspace
    qt=QApplication.instance() or QApplication([]);run(tmp_path/'engineering');a=StructuralProApp(tmp_path/'engineering'/'db')
    cmd(a,'building',id='B',title='بلوک');cmd(a,'floor',id='L1',title='طبقه اول',building_id='B',kind='positive',level=1,height='3.2');cmd(a,'discipline',id='S',title='سازه');cmd(a,'wbs',id='W',title='اسکلت',code='01',parent_id=None)
    cmd(a,'activity',id='ACT',title='سقف',code='A',wbs_id='W',floor_ids=['L1'],zone_ids=[],member_ids=['S1'],discipline_id='S',unit='m3',responsible='مسئول',status='todo',measurement={'kind':'none'})
    before=a.open_project('P');locations=a.activity_locations('P','ACT');assert len(locations)==1
    w=ProjectControlsWorkspace(a,'P');w.show();w.select_activity('ACT');qt.processEvents()
    try:
        QTest.mouseClick(w.findChild(QPushButton,'ActivityHighlight'),Qt.LeftButton)
        assert getattr(w,'drawing_window',None) is not None,w.status.text()
        assert w.drawing_window.canvas._highlighted_item_id==locations[0]['item_id']
        assert a.open_project('P')==before
        path=Path(locations[0]['path']);original=path.read_bytes();path.write_bytes(original+b'changed')
        try:
            import pytest
            with pytest.raises(ValueError):a.activity_locations('P','ACT')
        finally:path.write_bytes(original)
    finally:
        if getattr(w,'drawing_window',None):w.drawing_window.close()
        w.close();qt.processEvents();a.store.close()
