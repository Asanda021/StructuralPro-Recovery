import json, stat, sys
from pathlib import Path
from core.drawings.dwg_converter import OfflineDWGConverter
from core.drawings.dwg_takeoff import DWGTakeoffEngine
from core.drawings.pdf_graphical import GraphicalPDFTakeoff
from core.ai.hardware_profiles import select_profile, validate_model_manifest
from core.platform.mobile_runtime import AndroidRuntime, TelegramRuntime
from core.sync.memory import MemorySyncProvider
from core.sync.manager import SyncManager
from core.sync.offline_queue import OfflineQueue
from core.pricing.source_registry import PriceSource, PriceSourceRegistry
from core.platform.application import StructuralProApp


def _fake_converter(tmp_path):
    helper = tmp_path / "fake_dwg_converter.py"
    helper.write_text(
        "import pathlib, sys\n"
        "src, dst = map(pathlib.Path, sys.argv[1:3])\n"
        "data = src.read_bytes()\n"
        "dst.write_bytes(data[6:] if data.startswith(b'AC10') else data)\n",
        encoding="utf-8",
    )
    if sys.platform.startswith("win"):
        exe = tmp_path / "fake-dwg2dxf.bat"
        exe.write_text(
            f'@echo off\r\npython "{helper}" "%~1" "%~2"\r\n',
            encoding="utf-8",
        )
    else:
        exe = tmp_path / "fake-dwg2dxf"
        exe.write_text(
            f'#!/bin/sh\nexec python3 "{helper}" "$1" "$2"\n',
            encoding="utf-8",
        )
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def _minimal_dxf():
    return """0
SECTION
2
HEADER
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
WALL
10
0
20
0
11
3
21
4
0
ENDSEC
0
EOF
"""


def test_offline_dwg_converter_contract(tmp_path):
    exe = _fake_converter(tmp_path)
    src = tmp_path / "plan.dwg"
    # The production converter now validates output with ezdxf, so this contract
    # fixture must contain a real parseable DXF rather than arbitrary text.
    expected_dxf = _minimal_dxf()
    src.write_bytes(b"AC1032" + expected_dxf.encode("utf-8"))
    r = OfflineDWGConverter(str(exe)).convert(src, tmp_path / "out")
    assert r.output.read_text(encoding="utf-8") == expected_dxf


def test_dwg_engine_reads_converter_output(tmp_path, monkeypatch):
    exe = _fake_converter(tmp_path)
    src = tmp_path / "plan.dwg"
    src.write_bytes(b"AC1032" + _minimal_dxf().encode("utf-8"))
    monkeypatch.setenv("STRUCTURALPRO_DWG_CONVERTER", str(exe))
    doc = DWGTakeoffEngine().import_file(src)
    assert doc.entities[0].entity_type == "LINE"
    assert round(doc.entities[0].data["length"], 3) == 5.0


def test_graphical_pdf_geometry():
    m = GraphicalPDFTakeoff.line(1, 0, 0, 3, 4, 0.01)
    assert m.quantity == 0.05
    a = GraphicalPDFTakeoff.polygon(1, [(0, 0), (10, 0), (10, 10), (0, 10)], 0.1)
    assert round(a.quantity, 10) == 1


def test_ai_manifest_and_hardware(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"name": "demo", "format": "GGUF", "license": "Apache-2.0", "commercial_use": True, "sha256": "abc"}), encoding="utf-8")
    assert validate_model_manifest(p)["valid"]
    assert select_profile(16).name == "standard"


def test_mobile_clients_share_offline_runtime():
    for c in (AndroidRuntime(), TelegramRuntime()):
        assert c.open("P1")["id"] == "P1"
        assert c.command("open_project", project_id="P1").action == "open_project"


def test_e2e_sync_provider():
    p = MemorySyncProvider()
    p.push([{"project_id": "P1", "version": 1, "payload": {"name": "A"}}])
    p.push([{"project_id": "P1", "version": 2, "payload": {"name": "B"}}])
    assert p.pull("P1")[-1]["payload"]["name"] == "B"


def test_sync_manager_end_to_end(tmp_path):
    provider = MemorySyncProvider()
    manager = SyncManager(provider, OfflineQueue(tmp_path / "queue.json"))
    manager.record_local_change({"project_id": "P2", "version": 1, "payload": {"name": "A"}})
    result = manager.sync("P2")
    assert result.pushed == 1 and result.pulled == 1
    assert manager.queue.peek() == []


def test_price_source_registry():
    r = PriceSourceRegistry()
    s = PriceSource(1405, "ابنیه", "verified", "https://example.invalid", "licensed", "2026-10-01", "abc", True)
    r.add(s)
    assert r.verify_record(s, "abc")


def test_windows_shared_application_workflow(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه", "P1")
    app.add_takeoff("P1", "building", "slab", length=2, width=3, height=0.2, price_code="S1", unit_price=100)
    app.add_takeoff("P1", "building", "wall", length=4, height=3, price_code="W1", unit_price=50)
    p = app.open_project("P1")
    assert p["name"] == "پروژه" and len(p["takeoffs"]) == 2
    assert len(p["boq"]) == 2
    assert app.validate("P1") == []
