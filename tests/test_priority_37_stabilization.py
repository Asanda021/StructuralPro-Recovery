"""Priority 37 — stabilization-cycle regression and invariant tests."""
from __future__ import annotations
from pathlib import Path

def test_repeated_recalculation_is_stable(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/"data")
    app.create_project("Stable","S37")
    app.add_takeoff("S37","building","slab_volume",length=10,width=8,thickness=.2)
    first=app.recalculate_estimate("S37")
    second=app.recalculate_estimate("S37")
    assert first["boq"] == second["boq"]
    assert app.open_project("S37")["id"]=="S37"

def test_failed_mutation_does_not_leave_partial_rows(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/"data")
    app.create_project("Stable","S37")
    before=app.open_project("S37")
    try:
        app.add_takeoff("S37","building","slab_volume",length=-1,width=2,thickness=.2)
    except (ValueError,TypeError):
        pass
    assert app.open_project("S37")==before

def test_recovery_round_trip_after_recalculation(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/"data")
    app.create_project("Stable","S37")
    app.add_takeoff("S37","building","slab_volume",length=6,width=5,thickness=.2)
    expected=app.recalculate_estimate("S37")["boq"]
    path=tmp_path/"stable.json"
    app.export_project_backup("S37",path)
    restored=app.import_project_backup(path)
    assert restored["id"]=="S37"
    assert app.recalculate_estimate("S37")["boq"]==expected
