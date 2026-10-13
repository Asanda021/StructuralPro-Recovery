"""Structural GUI must not preselect geometry and must persist explicit physical shape."""
from pathlib import Path

UI = Path("app/reviewed_structural_manual_editor.py").read_text(encoding="utf-8")

def test_member_shape_selection_has_no_fabricated_rectangle():
    assert 'shape.addItem("نوع هندسه را صریح انتخاب کنید", None)' in UI
    assert 'if selected_shape not in {"rectangular", "circular_column", "reviewed_sections"}:' in UI
    assert 'raise ValueError("انتخاب صریح نوع هندسه برای عضو الزامی است")' in UI
    assert 'dimensions["shape"]=selected_shape' in UI
    assert 'if selected_shape!="rectangular"' not in UI
    assert 'shape.findData(geo.get("shape"))' in UI
    assert 'shape.findData(geo.get("shape","rectangular"))' not in UI
