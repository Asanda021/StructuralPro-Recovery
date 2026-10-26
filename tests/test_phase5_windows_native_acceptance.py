"""Native Windows P5-3 acceptance: actual access token, file owner and Qt UI.

No identity mocks: this test must run on a real Windows runner with PySide6.
The SID is recorded as a digest, never replaced with an environment username.
"""
from __future__ import annotations

import hashlib
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows")

def test_current_windows_token_principal_reaches_projectstore_and_real_qt_workspace(tmp_path, monkeypatch):
    from core.platform.identity import SystemIdentityProvider
    from core.platform.application import StructuralProApp
    from app.project_controls_workspace import ProjectControlsWorkspace
    from PySide6.QtWidgets import QApplication

    provider = SystemIdentityProvider()
    observed = provider.current()
    assert observed.platform == "windows"
    assert observed.authority == "windows-access-token"
    assert observed.authenticated and observed.subject_id.startswith("S-1-")
    monkeypatch.setenv("USERNAME", "spoofed-owner")
    monkeypatch.setenv("USER", "spoofed-owner")
    again = provider.current()
    assert again.subject_id == observed.subject_id
    assert again.display_name != "spoofed-owner"

    service = StructuralProApp(tmp_path / "workspace")
    service.create_project("پروژه آزمایشی ویندوز", "WINDOWS-NATIVE-P5")
    principal = service.store.current_principal("WINDOWS-NATIVE-P5")
    assert principal.user_id == observed.subject_id
    assert principal.role == "owner"
    assert service.open_project("WINDOWS-NATIVE-P5")["_meta"]["version"] == 1
    assert service.store.verify_audit("WINDOWS-NATIVE-P5") is True

    app = QApplication.instance() or QApplication([])
    window = ProjectControlsWorkspace(service, "WINDOWS-NATIVE-P5")
    window.show()
    app.processEvents()
    try:
        assert window.isVisible()
        assert service.store.current_principal("WINDOWS-NATIVE-P5").user_id == observed.subject_id
    finally:
        window.close()
        app.processEvents()

    db = service.store.path
    owner_sid = provider._windows_file_owner_sid(db)
    assert owner_sid.startswith("S-1-")
    print("WINDOWS_NATIVE_TOKEN_SID_SHA256", hashlib.sha256(observed.subject_id.encode()).hexdigest())
    print("WINDOWS_NATIVE_FILE_OWNER_SID_SHA256", hashlib.sha256(owner_sid.encode()).hexdigest())
    print("WINDOWS_NATIVE_OWNER_MATCH", owner_sid == observed.subject_id)
    service.store.close()
    reopened = StructuralProApp(tmp_path / "workspace")
    try:
        assert reopened.open_project("WINDOWS-NATIVE-P5")["_meta"]["version"] == 1
        assert reopened.store.verify_audit("WINDOWS-NATIVE-P5") is True
        assert reopened.store.current_principal("WINDOWS-NATIVE-P5").role == "owner"
    finally:
        reopened.store.close()
