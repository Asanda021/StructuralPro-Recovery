"""Priority 36 — full QA audit invariants."""
from __future__ import annotations
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_qa_surface_and_required_project_files():
    assert (ROOT/"VERSION").is_file()
    assert (ROOT/"packaging/build_windows.ps1").is_file()
    assert (ROOT/"packaging/installer.iss").is_file()
    assert (ROOT/"packaging/structuralpro.spec").is_file()
    assert (ROOT/"core/platform/hardening.py").is_file()

def test_no_common_debug_artifacts_in_source():
    bad=[]
    for p in (ROOT/"core").rglob("*.py"):
        s=p.read_text(encoding="utf-8",errors="ignore")
        if "breakpoint()" in s or "pdb.set_trace()" in s:
            bad.append(str(p))
    assert not bad, bad

def test_json_serialization_contract_is_stable():
    from core.platform.application import StructuralProApp
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        app=StructuralProApp(Path(td))
        try:
            app.create_project("QA","QA36")
            app.add_takeoff("QA36","building","slab_volume",length=2,width=3,thickness=.2)
            estimate=app.recalculate_estimate("QA36")
            json.dumps(estimate,ensure_ascii=False)
            json.dumps(app.open_project("QA36"),ensure_ascii=False)
        finally:
            app.store.close()

def test_core_python_files_compile():
    import py_compile
    for p in (ROOT/"core").rglob("*.py"):
        py_compile.compile(str(p),doraise=True)
