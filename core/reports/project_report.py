"""Professional deterministic report model and export contract."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable
import math

DEFAULT_COLUMNS = (
    ("item_no", "ردیف"),
    ("item_code", "کد آیتم"),
    ("price_code", "کد قیمت"),
    ("chapter", "فصل"),
    ("category", "دسته"),
    ("group", "گروه"),
    ("description", "شرح"),
    ("quantity", "مقدار"),
    ("unit", "واحد"),
    ("unit_price", "بهای واحد"),
    ("total", "مبلغ"),
    ("status", "وضعیت"),
    ("source_id", "منبع متره"),
    ("notes", "یادداشت"),
)

def normalize_report_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]

def report_columns(rows: Iterable[dict[str, Any]]) -> list[tuple[str, str]]:
    rows = list(rows)
    present = {key for row in rows for key in row}
    columns = [(key, label) for key, label in DEFAULT_COLUMNS if key in present]
    extras = sorted(present - {key for key, _ in DEFAULT_COLUMNS})
    columns.extend((key, key.replace("_", " ")) for key in extras)
    return columns

@dataclass
class ProjectReport:
    project_name: str
    rows: list[dict[str, Any]]
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.rows = normalize_report_rows(self.rows)
        self.summary = dict(self.summary or {})
        self.metadata = dict(self.metadata or {})

    def as_rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]

    def columns(self) -> list[tuple[str, str]]:
        return report_columns(self.rows)

    def validate(self) -> dict[str, Any]:
        errors = []
        if not str(self.project_name or "").strip():
            errors.append("missing_project_name")
        seen_item_numbers = set()
        for index, row in enumerate(self.rows, 1):
            if "description" in row:
                if not str(row.get("description") or "").strip():
                    errors.append(f"row_{index}:missing_description")
            elif "شرح" in row:
                if any(key in row for key in ("ردیف", "مقدار", "واحد", "کد فهرست‌بها")) and not str(row.get("شرح") or "").strip():
                    errors.append(f"row_{index}:missing_description")
            elif any(key in row for key in ("item_no", "item_code", "price_code", "quantity", "unit", "total")):
                errors.append(f"row_{index}:missing_description")
            number_key = "item_no" if "item_no" in row else "ردیف"
            if number_key in row and row.get(number_key) is not None:
                item_no = str(row.get(number_key)).strip()
                if not item_no:
                    errors.append(f"row_{index}:missing_item_no")
                if item_no in seen_item_numbers:
                    errors.append(f"row_{index}:duplicate_item_no:{item_no}")
                seen_item_numbers.add(item_no)
            for field in ("quantity", "unit_price", "total", "مقدار", "بهای واحد", "مبلغ"):
                if field in row and row.get(field) is not None:
                    try:
                        if isinstance(row[field], bool):
                            raise ValueError("boolean is not a report number")
                        value = float(row[field])
                    except (TypeError, ValueError, OverflowError):
                        errors.append(f"row_{index}:invalid_{field}")
                        continue
                    if not math.isfinite(value) or value < 0:
                        errors.append(f"row_{index}:invalid_{field}")
        return {"valid": not errors, "errors": errors, "line_count": len(self.rows)}

    def export(self, path, fmt):
        validation = self.validate()
        if not validation["valid"]:
            raise ValueError("invalid report: " + str(validation["errors"]))
        from .exporters import export_csv, export_xlsx, export_docx, export_pdf
        f = str(fmt).lower().lstrip(".")
        exporters = {"csv": export_csv, "xlsx": export_xlsx, "docx": export_docx, "pdf": export_pdf}
        if f not in exporters:
            raise ValueError(f"unsupported report format: {fmt}")
        return exporters[f](
            self.rows, path, title=self.project_name, summary=self.summary,
            metadata=self.metadata, columns=self.columns(),
        )

def build_report(project_name, rows, summary=None, metadata=None):
    return ProjectReport(project_name, list(rows), summary or {}, metadata or {})
