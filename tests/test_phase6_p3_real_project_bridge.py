"""Production integration: canonical SQLite review -> 2D/3D/tree/BOQ, never a mock approval."""
from copy import deepcopy
from hashlib import sha256

import pytest

from test_phase2_priority5_closure import identity_case
from core.drawings.project_selection_bridge import VerifiedProjectSelection


def reviewed(tmp_path):
    app,path,proof,proposal,args=identity_case(tmp_path)
    app.review_ifc_identity("P",**args)
    return app,path,proof,proposal


def make(app,path):
    from core.drawings.bim_adapter import BIMAdapter
    doc=BIMAdapter().read_document(path,revision="R1")
    return VerifiedProjectSelection(
        app,"P",source_sha256=sha256(path.read_bytes()).hexdigest(),
        revision="R1",real_global_ids={e["global_id"] for e in doc["elements"]})


def test_real_sqlite_review_resolves_2d_3d_tree_and_blocks_unapproved_boq(tmp_path):
    app,path,proof,proposal=reviewed(tmp_path)
    before=app.store.current_digest("P")
    graph=make(app,path)
    gid=proposal["global_id"]
    assert graph.resolve(origin="2d",identifier=gid,
        source_sha256=graph.source_sha256,revision="R1").member_ids==("B1",)
    assert graph.resolve(origin="3d",identifier=gid,
        source_sha256=graph.source_sha256,revision="R1").member_ids==("B1",)
    assert graph.resolve(origin="tree",identifier="B1",
        source_sha256=graph.source_sha256,revision="R1").global_ids==(gid,)
    assert graph.index.allowed["boq_row_id"] == frozenset()
    assert app.store.current_digest("P")==before
    assert app.open_project("P")["boq"]==[]
    app.store.close()


def test_no_persisted_review_means_unlinked_not_fabricated(tmp_path):
    app,path,proof,proposal,args=identity_case(tmp_path)
    graph=make(app,path)
    result=graph.resolve(origin="tree",identifier="B1",
        source_sha256=graph.source_sha256,revision="R1")
    assert result.status=="unlinked"
    assert graph.index.links==()
    app.store.close()


@pytest.mark.parametrize("change",["project", "proof", "source","revision","wrong_sha","wrong_member"])
def test_live_index_fails_closed_on_revision_and_tamper(tmp_path,change):
    app,path,proof,proposal=reviewed(tmp_path)
    graph=make(app,path)
    if change=="project":
        app.add_project_floor("P","طبقه دوم",level="F2")
    elif change=="proof":
        proof.write_text("tampered reviewed evidence",encoding="utf8")
    elif change=="source":
        path.write_bytes(path.read_bytes()+b"changed")
    elif change=="revision":
        with pytest.raises(RuntimeError):
            graph.assert_current(source_sha256=graph.source_sha256,revision="R2")
        app.store.close();return
    elif change=="wrong_sha":
        with pytest.raises(RuntimeError):
            graph.assert_current(source_sha256="c"*64,revision="R1")
        app.store.close();return
    elif change=="wrong_member":
        with pytest.raises(ValueError):
            VerifiedProjectSelection(app,"P",source_sha256=graph.source_sha256,
                revision="R1",real_global_ids={"not-the-real-GlobalId"})
        app.store.close();return
    # After-the-fact evidence mutations must not stay approved in navigation.
    if change in ("proof","source"):
        # Rebuild index fails on independently verified evidence, while
        # 'project' detects CAS at navigation time.
        with pytest.raises(ValueError):
            make(app,path)
    else:
        with pytest.raises(RuntimeError):
            graph.assert_current(source_sha256=graph.source_sha256,revision="R1")
    app.store.close()


def test_real_qt_workspace_four_way_button_and_2d_tree_sync(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,path,proof,proposal=reviewed(tmp_path)
    qt=QApplication.instance() or QApplication([])
    dialog=GraphicalTakeoffDialog(app_service=app,project_id="P")
    dialog.show()
    dialog.open_drawing(str(path))
    dialog.ifc_revision.setText("R1")
    assert dialog.verified_crossview_button.isVisible()
    digest=app.store.current_digest("P")
    QTest.mouseClick(dialog.verified_crossview_button,Qt.MouseButton.LeftButton)
    holder=dialog._verified_selection_dialog
    panel=dialog._verified_selection_panel
    assert holder is not None and panel is not None,dialog.status.text()
    gid=proposal["global_id"]
    assert panel.index.project_id=="P" and panel.index.source_sha256==digest[:0]+sha256(path.read_bytes()).hexdigest()
    dialog.highlight_ifc_member(gid)
    assert dialog._ifc_selected_global_id==gid
    assert panel.members.selectedItems() and panel.members.selectedItems()[0].text(0)=="B1"
    panel.members.topLevelItem(0).setSelected(False)
    panel._lookup("tree","B1")
    assert dialog._ifc_selected_global_id==gid
    assert app.store.current_digest("P")==digest
    assert dialog.session.items==[] and app.open_project("P")["boq"]==[]
    holder.close();dialog.close();qt.processEvents();app.store.close()


def test_real_qt_unreviewed_is_visible_but_unlinked(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,path,proof,proposal,args=identity_case(tmp_path)
    qt=QApplication.instance() or QApplication([])
    dlg=GraphicalTakeoffDialog(app_service=app,project_id="P")
    dlg.open_drawing(str(path))
    dlg.ifc_revision.setText("R1")
    pane=dlg.open_verified_crossview()
    assert pane is not None,dlg.status.text()
    panel=dlg._verified_selection_panel
    sent=[]
    panel.oneGlobalIdSelected.connect(sent.append)
    panel._lookup("tree","B1")
    assert not sent and "ارتباط" in panel.detail.text()
    pane.close();dlg.close();qt.processEvents();app.store.close()
