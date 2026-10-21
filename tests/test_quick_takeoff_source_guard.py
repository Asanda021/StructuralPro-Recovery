"""Quick takeoff requires explicit physical identity; no random source may bypass duplicate guard."""
import json
from pathlib import Path

import pytest
from core.platform.application import StructuralProApp


def test_quick_ui_contract_requires_real_floor_and_source():
    code = Path("app/main.py").read_text(encoding="utf-8")
    assert 'qfloor.setObjectName("QuickTakeoffFloor")' in code
    assert 'qsource.setObjectName("QuickTakeoffSource")' in code
    assert 'if not pid or not floor or not source:' in code
    assert 'source_id="manual-quick:"+json.dumps([pid,floor,source]' in code
    assert 'system=floor' in code
    assert 'source_id="manual:"+uuid4().hex' not in code


def test_one_physical_quick_source_cannot_be_double_billed_across_items(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("آزمون مستقل هویت متره سریع", "p")
    source = "manual-quick:" + json.dumps(["p", "L1", "inspection-1"], ensure_ascii=False, separators=(",", ":"))
    app.add_takeoff("p", "building", "slab", source_id=source, system="L1",
                    length=10, width=5, count=1)
    original = app.open_project("p")
    assert len(original["takeoffs"]) == 1 and len(original["boq"]) == 1
    with pytest.raises(ValueError, match="تکراری"):
        app.add_takeoff("p", "building", "slab", source_id=source, system="L1",
                        length=10, width=5, count=1)
    with pytest.raises(ValueError, match="تکراری"):
        app.add_takeoff("p", "building", "wall", source_id=source, system="L1",
                        length=10, height=3, openings=0, count=1)
    assert app.open_project("p")["takeoffs"] == original["takeoffs"]
    assert app.open_project("p")["boq"] == original["boq"]
    second = "manual-quick:" + json.dumps(["p", "L1", "inspection-2"], ensure_ascii=False, separators=(",", ":"))
    app.add_takeoff("p", "building", "slab", source_id=second, system="L1",
                    length=2, width=2, count=1)
    assert len(app.open_project("p")["takeoffs"]) == 2
    app.store.close()
