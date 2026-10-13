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


@pytest.fixture
def approve_test_pricebook(tmp_path):
    """Hash-checked, explicitly specified test catalog; never derive prices from BOQ."""
    import hashlib
    import json

    def approve(app, pid: str, prices: dict):
        assert prices and isinstance(prices, dict)
        for code, row in prices.items():
            assert code and isinstance(row, dict)
            assert set(row) == {"unit", "unit_price"}
            assert row["unit"] and isinstance(row["unit_price"], (int, float))
        catalog = tmp_path / f"pricebook-{pid}.json"
        catalog.write_text(
            json.dumps(prices, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        project = app.open_project(pid)
        project["user_pricebook_review"] = {
            "status": "approved", "approved_by": "test-fixture-reviewer",
            "path": str(catalog),
            "sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
            "rows_by_code": prices,
        }
        app.store.save(pid, project, expected_digest=app.store.current_digest(pid))
        return catalog
    return approve
