"""Unicode-safe CAD text normalization for the StructuralPro drawing viewer.

This module only normalizes annotation text. It never alters CAD geometry,
measurement units, or takeoff quantities.
"""
from __future__ import annotations

import re
import unicodedata

_UNICODE_ESCAPE = re.compile(r"\\U\+([0-9A-Fa-f]{4,8})")
_MTEXT_STACK = re.compile(r"\\[A-Za-z][^;]*;")
_FORMATTING = re.compile(r"\\[ACFHQWT][^;]*;")
_PERSIAN_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def normalize_cad_text(value: object) -> str:
    """Decode common DXF TEXT/MTEXT escapes while preserving Unicode content."""
    text = str(value or "")
    text = _UNICODE_ESCAPE.sub(lambda m: _codepoint(m.group(1)), text)
    text = text.replace(r"\P", "\n").replace(r"\p", "\n")
    text = text.replace(r"\~", "\u00a0")
    text = text.replace(r"\{", "{").replace(r"\}", "}")
    text = re.sub(r"^\{\\[A-Za-z][^;]*;", "", text)
    text = _FORMATTING.sub("", text)
    text = _MTEXT_STACK.sub("", text)
    text = text.replace("}", "")
    text = text.replace("%%d", "°").replace("%%D", "°")
    text = text.replace("%%p", "±").replace("%%P", "±")
    text = text.replace("%%c", "Ø").replace("%%C", "Ø")
    # Normalize equivalent Unicode forms without transliterating Persian text.
    return unicodedata.normalize("NFC", text).strip()


def _codepoint(hex_value: str) -> str:
    try:
        value = int(hex_value, 16)
        if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
            return "\uFFFD"
        return chr(value)
    except (TypeError, ValueError):
        return "\uFFFD"


def is_rtl_cad_text(value: object) -> bool:
    """True when text contains Arabic/Persian/Hebrew presentation characters."""
    return bool(_PERSIAN_ARABIC.search(normalize_cad_text(value)))


def cad_text_height(entity_data: dict, default: float = 2.5) -> float:
    """Return a safe positive annotation height from parsed entity metadata."""
    for key in ("height", "char_height", "text_height"):
        try:
            height = float(entity_data.get(key, 0))
        except (TypeError, ValueError):
            continue
        if height > 0 and height < 1e7:
            return height
    return default
