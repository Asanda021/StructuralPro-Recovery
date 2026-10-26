from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from app.project_controls_workspace import ProjectControlsWorkspace
from core.platform.application import StructuralProApp
from test_phase5_p3_trusted_identity_store import SwitchingIdentityProvider, identity


QT = QApplication.instance() or QApplication([])


def test_real_project_controls_ui_cannot_spoof_owner_actor_to_bypass_viewer_acl(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    service = StructuralProApp(tmp_path, identity_provider=identities)
    service.create_project("پروژه کنترل مجوز", "P")
    service.store.grant_role("P", "subject:B", "viewer", reference="test:viewer")
    before = service.open_project("P")

    identities.identity = identity("subject:B", "Bob")
    window = ProjectControlsWorkspace(service, "P")
    window.show()
    QT.processEvents()
    try:
        # The legacy field is deliberately spoofed.  Authorization must use the
        # OS-bound store principal, not this text value.
        window.fields["actor"].setText("owner")
        window.fields["reason"].setText("تلاش جعل نقش از رابط")
        window.fields["calendar_start"].setText("۱۴۰۴/۱۰/۱۱")
        window.fields["weekdays"].setText("0,1,2,3,4,5,6")
        window.fields["holidays"].clear()
        QTest.mouseClick(window.findChild(QPushButton, "ScheduleCalendarSave"), Qt.LeftButton)
        QT.processEvents()
    finally:
        window.close()
        QT.processEvents()

    identities.identity = identity("subject:A", "Alice")
    after = service.open_project("P")
    assert after["_meta"]["version"] == before["_meta"]["version"]
    assert after.get("project_control_config") == before.get("project_control_config")
    assert any(
        event["status"] == "failure" and event["actor"] == "subject:B"
        for event in service.store.audit_events("P")
    )

