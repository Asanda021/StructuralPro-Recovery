from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class PriceBookRow:
    year: int
    item_code: str
    description: str
    unit: str
    rate: float
    source_id: str


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _parse_rows(rows, source_id: str) -> list[PriceBookRow]:
    out: list[PriceBookRow] = []
    for row in rows:
        year = int(_clean(row.get("year", "")))
        code = _clean(row.get("item_code", ""))
        desc = _clean(row.get("description", ""))
        unit = _clean(row.get("unit", ""))
        rate = float(_clean(row.get("rate", "")))
        if year < 1300 or not code or not desc or not unit or rate < 0:
            raise ValueError("invalid price-book row")
        out.append(PriceBookRow(year, code, desc, unit, rate, source_id))
    return out


def import_csv(content: str, source_id: str) -> list[PriceBookRow]:
    reader = csv.DictReader(io.StringIO(content))
    required = {"year", "item_code", "description", "unit", "rate"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV must contain year,item_code,description,unit,rate")
    return _parse_rows(reader, source_id)


def _xlsx_cells(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//m:t", ns)))
        sheet = next(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        root = ET.fromstring(zf.read(sheet))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        matrix: dict[int, dict[int, str]] = {}
        for cell in root.findall(".//m:c", ns):
            ref = cell.attrib.get("r", "")
            m = re.match(r"([A-Z]+)(\d+)", ref)
            if not m:
                continue
            col = 0
            for ch in m.group(1):
                col = col * 26 + ord(ch) - 64
            row = int(m.group(2))
            value = cell.find("m:v", ns)
            text = "" if value is None else (value.text or "")
            if cell.attrib.get("t") == "s" and text:
                text = shared[int(text)]
            matrix.setdefault(row, {})[col] = text
        return [[matrix[r].get(c, "") for c in range(1, max((max(v) for v in matrix.values()), default=0) + 1)] for r in sorted(matrix)]


def import_xlsx(content: bytes, source_id: str) -> list[PriceBookRow]:
    rows = _xlsx_cells(content)
    if not rows:
        raise ValueError("empty XLSX")
    headers = [_clean(x).lower() for x in rows[0]]
    required = ["year", "item_code", "description", "unit", "rate"]
    if not set(required).issubset(headers):
        raise ValueError("XLSX must contain year,item_code,description,unit,rate")
    indexes = {name: headers.index(name) for name in required}
    records = []
    for row in rows[1:]:
        records.append({name: row[index] if index < len(row) else "" for name, index in indexes.items()})
    return _parse_rows(records, source_id)


def dataset_fingerprint(rows: list[PriceBookRow]) -> str:
    canonical = "\n".join(
        f"{r.year}|{r.item_code}|{r.description}|{r.unit}|{r.rate:.12g}|{r.source_id}"
        for r in sorted(rows, key=lambda x: (x.year, x.item_code, x.source_id))
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def year_coverage(rows: list[PriceBookRow], requested_years: set[int]) -> dict:
    present = {r.year for r in rows}
    missing = sorted(requested_years - present)
    return {"requested": sorted(requested_years), "present": sorted(present), "missing": missing,
            "complete": not missing}
