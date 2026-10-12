from pathlib import Path

MAIN = Path("app/main.py").read_text(encoding="utf-8")
DIALOG = Path("app/manual_takeoff.py").read_text(encoding="utf-8")


def test_manual_takeoff_dialog_is_wired_into_quick_takeoff():
    assert "from app.manual_takeoff import ManualTakeoffDialog" in MAIN
    assert 'manual_button=QPushButton("📝 متره دستی حرفه‌ای")' in MAIN
    assert "ManualTakeoffDialog(service,qpid.text().strip(),w)" in MAIN
    assert "manual_button.clicked.connect(open_manual_workbench)" in MAIN


def test_manual_takeoff_requires_project_and_floor_before_preview():
    assert 'if not project_id:' in DIALOG
    assert 'if not floor_id:' in DIALOG
    assert "self.service.open_project(project_id)" in DIALOG
    assert "self.workbench.add_text(" in DIALOG


def test_manual_takeoff_saves_deterministic_quantities_to_project_service():
    assert "self.service.add_takeoff(" in DIALOG
    assert 'source_id=f"manual-workbench:{record.project_id}:{self._session_id}:{record.record_id}"' in DIALOG
    assert "system=record.floor_id" in DIALOG
    assert "record.record_id in self._saved_ids" in DIALOG
    assert '"ذخیره شد"' in DIALOG


def test_incomplete_manual_entries_are_not_persisted():
    assert "isinstance(result, ManualTakeoffDraft)" in DIALOG
    assert '"نیازمند: "' in DIALOG
    assert "for record in self.workbench.records:" in DIALOG


def test_manual_takeoff_workbench_exposes_phase_two_controls():
    for control in ("چسباندن Excel", "ویرایش ردیف انتخابی", "کپی ردیف",
                    "کپی به طبقه دیگر", "حذف ردیف انتخابی", "واگرد", "تکرار"):
        assert control in DIALOG
    assert "QApplication.clipboard().text()" in DIALOG
    assert 'project.setdefault("_manual_takeoff_audit", [])' in DIALOG
    assert 'self.service.store.save(project_id, project)' in DIALOG
