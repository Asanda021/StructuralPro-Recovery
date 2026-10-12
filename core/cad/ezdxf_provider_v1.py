"""Licensed/open DXF provider boundary for StructuralPro.

Uses ezdxf for real DXF parsing. DWG is deliberately fail-closed here:
ezdxf is a DXF library, not a native DWG parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ezdxf


@dataclass(frozen=True)
class DXFEntityEvidence:
    entity_type: str
    layer: str
    handle: str


@dataclass(frozen=True)
class DXFDocumentEvidence:
    path: str
    dxf_version: str
    entities: tuple[DXFEntityEvidence, ...]
    layers: tuple[str, ...]
    blocks: tuple[str, ...]


class CADProviderError(ValueError):
    pass


def read_dxf(path: str | Path) -> DXFDocumentEvidence:
    source = Path(path)
    if source.suffix.lower() != ".dxf":
        raise CADProviderError("DXF provider accepts .dxf only; DWG requires an authorized provider")
    if not source.is_file():
        raise CADProviderError("CAD source file does not exist")
    try:
        doc = ezdxf.readfile(source)
    except Exception as exc:
        raise CADProviderError(f"DXF parsing failed: {exc}") from exc

    msp = doc.modelspace()
    entities = tuple(
        DXFEntityEvidence(
            entity_type=entity.dxftype(),
            layer=str(entity.dxf.layer),
            handle=str(entity.dxf.handle or ""),
        )
        for entity in msp
    )
    layers = tuple(sorted({e.layer for e in entities}))
    blocks = tuple(sorted(block.name for block in doc.blocks if block.name))
    return DXFDocumentEvidence(
        path=str(source),
        dxf_version=str(doc.dxfversion),
        entities=entities,
        layers=layers,
        blocks=blocks,
    )


def read_cad(path: str | Path) -> DXFDocumentEvidence:
    """Canonical open-provider entry point; unsupported formats fail closed."""
    source = Path(path)
    if source.suffix.lower() == ".dxf":
        return read_dxf(source)
    if source.suffix.lower() == ".dwg":
        raise CADProviderError(
            "No bundled native DWG parser is authorized. Install/configure an authorized DWG provider."
        )
    raise CADProviderError("Unsupported CAD format")
