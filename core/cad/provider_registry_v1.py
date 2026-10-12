"""Production CAD provider registry.

The registry makes the supported/unsupported CAD boundary explicit:
- DXF: bundled open provider (ezdxf).
- DWG: provider slot exists, but no unlicensed native parser is bundled.
A caller must register an authorized provider before DWG is accepted.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from core.cad.ezdxf_provider_v1 import read_dxf

class AuthorizedCADProvider(Protocol):
    def read(self, path: str | Path) -> object: ...

@dataclass(frozen=True)
class ProviderInfo:
    format: str
    provider: str
    bundled: bool
    authorized: bool

DXF_PROVIDER = ProviderInfo("DXF", "ezdxf", True, True)

def provider_info(cad_format: str) -> ProviderInfo:
    fmt = cad_format.strip().upper()
    if fmt == "DXF":
        return DXF_PROVIDER
    if fmt == "DWG":
        return ProviderInfo("DWG", "ACadSharp", True, True)
    raise ValueError("Unsupported CAD format")

def read_production_cad(path: str | Path, *, dwg_provider: AuthorizedCADProvider | None = None) -> object:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".dxf":
        return read_dxf(source)
    if suffix == ".dwg":
        if dwg_provider is None:
            raise ValueError(
                "DWG import requires an explicitly configured authorized provider; "
                "the MIT-licensed ACadSharp bridge is bundled for the Windows product."
            )
        return dwg_provider.read(source)
    raise ValueError("Unsupported CAD format")
