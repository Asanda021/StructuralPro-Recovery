"""Synthetic regressions: the existing physical-ID rule spans detail lines."""
from copy import deepcopy

import pytest

from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import preview_system
from core.platform.application import StructuralProApp
from test_phase1_cement_render_net_surface_chat import document


@pytest.mark.parametrize("alias", ["wall-face-1", "WALL-FACE-۱", "ＷＡＬＬ-ＦＡＣＥ-１"])
def test_unicode_physical_face_cannot_be_rebilled_through_another_detail_line(alias):
    draft = document()
    items = draft["components"]["render_coat"]["items"]
    second = deepcopy(items[0])
    second["line_id"] = "SURFACE-2"
    second["details"]["entries"][0]["id"] = alias
    items.append(second)
    result = preview_system(draft, TakeoffEngine())
    assert not result["ready"]
    assert result["rows"] == []
    assert any("تکراری" in message for message in result["blockers"])


def test_distinct_detail_faces_remain_valid_and_keep_exact_source_labels():
    draft = document()
    items = draft["components"]["render_coat"]["items"]
    second = deepcopy(items[0])
    second["line_id"] = "SURFACE-2"
    second["source_ref"] = "synthetic:source:case-sensitive"
    second["details"]["entries"][0]["id"] = "WALL-FACE-2"
    items.append(second)
    result = preview_system(draft, TakeoffEngine())
    assert result["ready"], result["blockers"]
    assert len(result["rows"]) == 2
    assert result["rows"][1]["source_ref"] == second["source_ref"]


def test_alias_double_count_cannot_commit_or_change_nonempty_sqlite_boq(tmp_path):
    app = StructuralProApp(tmp_path)
    try:
        app.create_project("Synthetic duplicate face", "P")
        app.add_takeoff("P", "building", "column", source_id="SYNTHETIC:EXISTING",
                        system="OTHER", manual_location_id="COL",
                        count=1, width=0.4, depth=0.4, height=3)
        draft = document()
        rows = draft["components"]["render_coat"]["items"]
        second = deepcopy(rows[0])
        second["line_id"] = "SURFACE-2"
        second["details"]["entries"][0]["id"] = "wall-face-۱"
        rows.append(second)
        app.save_aec_system_draft("P", draft, expected_revision=0)
        before = app.open_project("P")
        assert before["boq"]
        digest = app.store.current_digest("P")
        with pytest.raises(ValueError):
            app.commit_aec_system("P", "cement_render", "L1", "WALL-RENDER-1", expected_revision=1)
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()
