"""Shared pytest configuration for StructuralPro tests."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def nonblocking_error_dialogs(monkeypatch):
    """Preserve error results while keeping unattended Qt tests from hanging.

    This never accepts engineering confirmation dialogs. Tests still assert
    application output, persisted rows and quantities after the real callback.
    """
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtWidgets import QMessageBox
    messages = []
    def record(parent, title, message, *args, **kwargs):
        messages.append((str(title), str(message)))
        return QMessageBox.StandardButton.Ok
    for method in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, method, record)
    return messages
