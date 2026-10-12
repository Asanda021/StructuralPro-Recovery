"""Strict validation for imported annual price-list rows."""
from __future__ import annotations
import re
from typing import Iterable, Any

CODE_RE = re.compile(r"^[0-9۰-۹][0-9۰-۹.\-_/]*$")

def normalize_digits(value: Any) -> str:
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    return str(value).translate(table)

def normalize_code(value: Any) -> str:
    return normalize_digits(value).strip().replace(" ", "")

def validate_price_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        code = normalize_code(row.get("code", ""))
        unit = str(row.get("unit", "")).strip()
        desc = str(row.get("description", "")).strip()
        try:
            price = float(row.get("unit_price"))
        except (TypeError, ValueError):
            price = None
        if not code or not CODE_RE.match(code):
            errors.append({"row": index, "field": "code", "error": "invalid_code"})
        if not desc:
            errors.append({"row": index, "field": "description", "error": "missing_description"})
        if not unit:
            errors.append({"row": index, "field": "unit", "error": "missing_unit"})
        if price is None or price < 0:
            errors.append({"row": index, "field": "unit_price", "error": "invalid_price"})
    return errors
