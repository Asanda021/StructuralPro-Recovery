"""The real manual dialog audit must not overwrite another desktop's takeoff."""
from core.platform.application import StructuralProApp


def test_stale_dialog_preview_audit_preserves_other_instance_takeoff(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.manual_takeoff import ManualTakeoffDialog
    qt = QApplication.instance() or QApplication([])
    first = StructuralProApp(tmp_path)
    first.create_project("پروژه هم‌زمان", "p")
    second = StructuralProApp(tmp_path)
    dialog = ManualTakeoffDialog(second, "p")  # primes second desktop's stale cache
    first.add_takeoff("p", "building", "slab_volume", length=2, width=2,
                      thickness=1, source_id="other-desktop")
    dialog._audit("preview_added", {"complete": 0})
    first.store.close()
    second.store.close()
    reopened = StructuralProApp(tmp_path)
    data = reopened.open_project("p")
    assert len(data["takeoffs"]) == 1
    assert data["takeoffs"][0]["source_id"] == "other-desktop"
    assert data["_manual_takeoff_audit"][-1]["event"] == "preview_added"
    reopened.store.close()
    dialog.close()


def test_audit_conflict_preserves_committed_data_and_shows_warning(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app.manual_takeoff import ManualTakeoffDialog
    qt = QApplication.instance() or QApplication([])
    first = StructuralProApp(tmp_path)
    first.create_project("پروژه هم‌زمان", "p")
    other = StructuralProApp(tmp_path)
    dialog = ManualTakeoffDialog(first, "p")
    save = first.store.save

    def overlapping_save(pid, payload, *, expected_digest=None):
        other.add_takeoff("p", "building", "slab_volume", length=2, width=2,
                          thickness=1, source_id="concurrent-desktop")
        return save(pid, payload, expected_digest=expected_digest)

    # Only coordinate a real concurrent SQLite commit; no fake service/database.
    monkeypatch.setattr(first.store, "save", overlapping_save)
    dialog._audit("preview_added")
    first.store.close()
    other.store.close()
    reopened = StructuralProApp(tmp_path)
    project = reopened.open_project("p")
    assert len(project["takeoffs"]) == 1
    assert project["takeoffs"][0]["source_id"] == "concurrent-desktop"
    assert not project.get("_manual_takeoff_audit")
    assert "ممیزی ناموفق" in dialog.status.text()
    reopened.store.close()
    dialog.close()
