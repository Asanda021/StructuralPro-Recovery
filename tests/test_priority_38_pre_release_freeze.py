"""Priority 38 — final pre-release freeze guardrails."""
from __future__ import annotations
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def test_version_is_canonical():
    v=(ROOT/"VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+",v)

def test_no_release_blocker_markers_in_core():
    markers=("TODO_RELEASE_BLOCKER","FIXME_RELEASE_BLOCKER")
    hits=[]
    for p in (ROOT/"core").rglob("*.py"):
        s=p.read_text(encoding="utf-8",errors="ignore")
        if any(m in s for m in markers): hits.append(str(p))
    assert not hits

def test_release_surfaces_remain_present():
    for p in ("packaging/build_windows.ps1","packaging/installer.iss","packaging/structuralpro.spec",".github/workflows/windows-smoke.yml"):
        assert (ROOT/p).is_file(), p

def test_freeze_smoke_project(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/"data")
    app.create_project("Freeze","F38")
    app.add_takeoff("F38","building","slab_volume",length=4,width=5,thickness=.2)
    result=app.recalculate_estimate("F38")
    assert result["boq"]
    assert app.open_project("F38")["id"]=="F38"
