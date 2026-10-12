"""Deterministic RTL report/export contract."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import unicodedata

RTL_MARK = "\u200f"

@dataclass(frozen=True)
class ReportCell:
    key: str
    value: str

@dataclass(frozen=True)
class ReportSection:
    title: str
    cells: tuple[ReportCell, ...]

def normalize_persian(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("report values must be strings")
    value = unicodedata.normalize("NFC", value).replace("\u200e", "").replace("\u200f", "")
    return value.strip()

def render_rtl(sections: tuple[ReportSection, ...]) -> str:
    if not sections:
        raise ValueError("report must contain at least one section")
    lines = [RTL_MARK + "StructuralPro"]
    for section in sections:
        title = normalize_persian(section.title)
        if not title:
            raise ValueError("section title is required")
        lines.append(f"{RTL_MARK}{title}")
        for cell in section.cells:
            key = normalize_persian(cell.key)
            value = normalize_persian(cell.value)
            if not key:
                raise ValueError("cell key is required")
            lines.append(f"{RTL_MARK}{key}: {value}")
    return "\n".join(lines) + "\n"

def report_fingerprint(sections: tuple[ReportSection, ...]) -> str:
    return sha256(render_rtl(sections).encode("utf-8")).hexdigest()
