"""Static acceptance of actual P13–P15 UI wiring; no PySide6 needed."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def contents(path):
    return (ROOT/path).read_text(encoding="utf-8")


def test_all_new_persian_editor_modules_are_valid_python_syntax():
    for name in (
        "app/reviewed_aec_manual_editor.py",
        "app/reviewed_structural_manual_editor.py",
        "core/takeoff/reviewed_detail_calculators.py",
        "core/takeoff/reviewed_structural.py",
        "core/takeoff/reviewed_aec.py",
        "core/takeoff/assembly.py",
        "app/aec_workspace.py",
    ):
        ast.parse(contents(name),filename=name)


def test_main_aec_workspace_has_real_reviewed_editor_entrypoints():
    source=contents("app/aec_workspace.py")
    assert "open_reviewed_aec_editor(" in source
    assert "open_manual_structural_editor(" in source
    assert "complete_editor.clicked.connect(open_complete_editor)" in source
    assert "structural_editor.clicked.connect(open_structural_editor)" in source
    assert "service.add_assembly_takeoff(" in source


def test_manual_aec_editor_buttons_call_real_service_not_fake_success():
    text=contents("app/reviewed_aec_manual_editor.py")
    for symbol in (
        "get_aec_system(", "save_aec_system_draft(",
        "commit_aec_system(", "preview_system(",
        "source_id", "measurement_ref", "approved_by",
    ):
        assert symbol in text
    assert 'if state["changed"]:' in text
    assert 'if state["revision"] < 1:' in text
    assert "load_button.clicked.connect(load)" in text


def test_structural_editor_uses_real_revision_and_component_gates():
    text=contents("app/reviewed_structural_manual_editor.py")
    for symbol in (
        "get_structural_member(", "new_structural_member(",
        "save_structural_member_draft(", "commit_structural_member(",
        "preview_member(", "area_scope", "count_scope",
        "unit_weight_source", "start_m", "end_m", "approved_by",
    ):
        assert symbol in text
    assert 'if state["dirty"]:' in text


def test_joist_assembly_cannot_use_ceil_spacing_guess():
    text=contents("core/takeoff/assembly.py")
    section=text.split(
        'if k in {"joist_foam_roof_assembly", "joist_block_roof_assembly", "سقف_تیرچه_یونولیت"}:'
    )[1].split('if k in {"concrete_column", "column_concrete"}:')[0]
    assert 'physical_joists = _count(p, "joist_count")' in section
    assert 'infill_count = _count(p, infill + "_count")' in section
    assert "ceil(W / spacing)" not in section
    assert "ceil((area /" not in section
    assert "cast_rib_count" in section
    assert "mesh_unit_weight_source" in section


def test_atomic_manual_assembly_needs_physical_source_and_named_reviewer():
    text=contents("core/platform/application.py")
    section=text.split("    def add_assembly_takeoff(")[1].split(
        "    def revise_takeoff(")[0]
    assert "measurement_source" in section
    assert "approved_by" in section
    assert 'if not measurement or not reviewer:' in section
    assert 'bundle_source=f"manual-assembly:{pid}:{floor}:{measurement}"' in section
    assert "validate_commit_rows(" in section
    assert "rebuild_project_boq(" in section
