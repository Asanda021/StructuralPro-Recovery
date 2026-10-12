"""End-to-end acceptance gate for the five commercial core areas."""
import os
import stat

from core.drawings.dwg_converter import OfflineDWGConverter
from core.drawings.dwg_takeoff import DWGTakeoffEngine
from core.drawings.ifc_inventory import normalize_bim_rows, map_bim_to_price
from core.drawings.pdf_measurement import PDFMeasurementSession
from core.commercial.progress import build_progress
from core.pricing.catalog import PriceCatalog, PriceItem
from core.reports.quality import prepare_rows, summary


def _fake_converter(tmp_path):
    helper = tmp_path / "fake_dwg_converter.py"
    helper.write_text(
        "import pathlib, sys\n"
        "src, dst = map(pathlib.Path, sys.argv[1:3])\n"
        "data = src.read_bytes()\n"
        "dst.write_bytes(data[6:] if data.startswith(b'AC10') else data)\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        exe = tmp_path / "dwg2dxf.cmd"
        exe.write_text(f'@echo off\r\npython "{helper}" "%~1" "%~2"\r\n', encoding="utf-8")
    else:
        exe = tmp_path / "dwg2dxf"
        exe.write_text(f'#!/bin/sh\nexec python3 "{helper}" "$1" "$2"\n', encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def _dxf():
    return """0
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


def test_five_core_areas_end_to_end(tmp_path, monkeypatch):
    pdf = PDFMeasurementSession()
    pdf.calibrate(1000, 10, "m")
    line = pdf.add_length(1, [(0, 0), (300, 400)], label="دیوار")
    area = pdf.add_area(1, [(0, 0), (1000, 0), (1000, 1000), (0, 1000)],
                        holes=[[(200, 200), (400, 200), (400, 400), (200, 400)]],
                        label="کف")
    assert round(line.quantity, 6) == 5.0
    assert round(area.quantity, 6) == 96.0

    exe = _fake_converter(tmp_path)
    source = tmp_path / "plan.dwg"
    source.write_bytes(b"AC1032" + _dxf().encode("utf-8"))
    monkeypatch.setenv("STRUCTURALPRO_DWG_CONVERTER", str(exe))
    converted = OfflineDWGConverter(str(exe)).convert(source, tmp_path / "out")
    assert converted.output.exists()
    drawing = DWGTakeoffEngine().import_file(source)
    assert drawing.entities and drawing.entities[0].data["length"] == 5.0

    bim = normalize_bim_rows([
        {"global_id": "A", "ifc_type": "IfcWall", "properties": {"Level": "1"}, "quantities": {"Length": 5}},
        {"global_id": "A", "ifc_type": "IfcWall", "properties": {"Level": "1"}, "quantities": {"Length": 5}},
    ])
    mapped = map_bim_to_price(bim, {"IfcWall": "W001"}, strict=True)
    assert len(mapped) == 1 and mapped[0]["price_code"] == "W001"

    catalog = PriceCatalog([
        PriceItem(1404, "ابنیه", "فصل 1", "W001", "دیوار", "m", 1000),
        PriceItem(1405, "ابنیه", "فصل 1", "W001", "دیوار", "m", 1200),
    ])
    assert catalog.get("W001", 1404).unit_price == 1000
    assert catalog.get("W001", 1405).unit_price == 1200

    progress = build_progress(
        [{"contract_quantity": line.quantity, "previous_quantity": 2, "current_quantity": 1, "unit_price": 1200}],
        deductions=[100], payments=[500],
    )
    assert progress["lines"][0]["cumulative_quantity"] == 3
    assert progress["payable_current"] == 1100
    assert progress["balance_current"] == 600

    rows = prepare_rows([{"source": "PDF", "price_code": "W001", "description": "دیوار",
                          "quantity": 1, "unit": "m", "unit_price": 1200}], "fa")
    assert summary(rows)["grand_total"] == 1200
    assert summary(rows)["rtl"] is True
