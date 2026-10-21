"""Offline static contract: AEC table has accountable source identity and connected actions."""
import ast
from pathlib import Path

SRC = Path('app/aec_workspace.py').read_text(encoding='utf-8')
MAIN = Path('app/main.py').read_text(encoding='utf-8')

def test_ui_source_identity_is_from_takeoff_not_quantity_fallback():
    assert 'rows=[(t,q) for t in p.get("takeoffs",[])' in SRC
    assert 'takeoff.get("source_id","") or "—"' in SRC
    assert 'takeoff.get("id","")' in SRC
    assert 'q.get("source","manual")' not in SRC
    assert 'except Exception as exc:' in SRC
    assert 'result.setText("خطا در خواندن ریزمتره پروژه: " + str(exc))' in SRC

def test_persian_ribbon_actions_are_bound_to_real_slot_callbacks():
    root = ast.parse(MAIN)
    assert any(isinstance(node,ast.FunctionDef) and node.name=='refresh_command_ribbon'
               for node in ast.walk(root))
    assert 'button.clicked.connect(callback)' in MAIN
    assert 'pages.currentChanged.connect(refresh_command_ribbon)' in MAIN
    assert 'navigation_tabs.currentChanged.connect(navigate_from_tab)' in MAIN
    assert 'pages.currentChanged.connect(sync_tabs_to_page)' in MAIN
    assert 'QTabBar()' in MAIN
    assert 'QShortcut(QKeySequence("F1")' in MAIN

def test_aec_manual_editor_is_reachable_and_commits_real_service():
    assert 'complete_editor.clicked.connect(open_complete_editor)' in SRC
    assert 'structural_editor.clicked.connect(open_structural_editor)' in SRC
    assert 'calc.clicked.connect(calculate)' in SRC
    assert 'service.add_assembly_takeoff(' in SRC
    assert 'row=service.add_takeoff(' in SRC
    assert 'if code in {"waffle_roof","uboot_roof","cobiax_roof","hollow_core_roof","steel_roof_composite_concrete"}:' in SRC
