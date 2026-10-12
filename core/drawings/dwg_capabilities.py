"""Transparent DWG capability diagnostics for the current production backend."""
from __future__ import annotations
from dataclasses import dataclass
import os, shutil
from pathlib import Path


@dataclass(frozen=True)
class DWGCapabilities:
    native_reader: bool
    converter: str | None
    converter_kind: str | None
    message: str


def detect_dwg_capabilities() -> DWGCapabilities:
    env = os.getenv("STRUCTURALPRO_DWG_CONVERTER")
    candidates = [env, shutil.which("ODAFileConverter"), shutil.which("dwg2dxf"), shutil.which("TeighaFileConverter")]
    converter = next((x for x in candidates if x), None)

    # libredwg is intentionally reported as installed-only: the production
    # extraction path currently uses the validated DXF parser after conversion.
    try:
        import libredwg  # type: ignore  # noqa: F401
        native = True
    except Exception:
        native = False

    kind = None
    if converter:
        name = Path(converter).name.lower()
        kind = "oda" if "oda" in name else ("teigha" if "teigha" in name else "generic")

    if converter:
        msg = f"DWG: مبدل آفلاین {kind} فعال است؛ خروجی با parser واقعی DXF تحلیل می‌شود."
    elif native:
        msg = "libredwg روی سیستم نصب است، اما backend فعال پروژه هنوز parser مستقیم آن نیست؛ برای DWG از ODAFileConverter/dwg2dxf استفاده کنید."
    else:
        msg = "DWG Reader/Converter فعال نیست؛ ODAFileConverter یا dwg2dxf را نصب کنید. DXF مستقیم قابل تحلیل است."

    return DWGCapabilities(native, converter, kind, msg)
