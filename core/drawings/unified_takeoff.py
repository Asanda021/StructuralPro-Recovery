"""Unified offline drawing takeoff boundary with explicit confirmation."""
from __future__ import annotations

from pathlib import Path
import math
from typing import Any

from core.drawings.pdf_takeoff import PDFTakeoffAdapter
from core.drawings.dwg_takeoff import DWGTakeoffEngine
from core.drawings.bim_quantities import read_ifc
from core.drawings.auto_takeoff import generate_auto_takeoff
from core.ai.auto_takeoff import LocalAutoTakeoff
from core.drawings.review import review_candidates

_BIM_UNITS = {
    "Length": "m", "Width": "m", "Height": "m", "Area": "m2",
    "NetArea": "m2", "GrossArea": "m2", "Volume": "m3",
    "NetVolume": "m3", "GrossVolume": "m3", "Count": "عدد",
}


class UnifiedDrawingTakeoff:
    def __init__(self, price_resolver=None):
        self.price_resolver = price_resolver
        self.auto = LocalAutoTakeoff()
        self.last_review_audit = None

    def inspect(self, path: str | Path) -> dict[str, Any]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        ext = p.suffix.lower()

        if ext == ".pdf":
            adapter = PDFTakeoffAdapter()
            pages = adapter.inspect(p)
            candidates = adapter.text_takeoff_candidates(pages)
            scales = self.auto.auto_scale("\n".join(x.text for x in pages))
            return {
                "kind": "pdf", "source": str(p), "pages": len(pages),
                "scale_candidate": scales, "candidates": candidates,
            }

        if ext in {".dwg", ".dxf"}:
            engine = DWGTakeoffEngine()
            doc = engine.import_file(p)
            scale_text = "\n".join(doc.text_labels)
            auto = generate_auto_takeoff(
                doc.entities,
                scale_text=scale_text,
                source_unit=doc.units,
                sheet=p.stem,
            )
            return {
                "kind": "cad",
                "source": str(p),
                "summary": engine.summarize(doc),
                "scale": auto["scale"],
                "candidates": auto["candidates"],
                "auto_takeoff_summary": auto["summary"],
                "document": doc,
            }

        if ext in {".ifc", ".ifczip"}:
            rows = read_ifc(p)
            candidates = []
            for row in rows:
                for key, value in row.get("quantities", {}).items():
                    candidates.append({
                        "source": f'ifc:{row.get("global_id", "") or row.get("name", "")}:{key}',
                        "description": f'{row.get("ifc_type", "")} {row.get("name", "")} {key}',
                        "quantity": value,
                        "unit": _BIM_UNITS.get(key, "unknown"),
                        "needs_confirmation": True,
                    })
            return {"kind": "bim", "source": str(p), "objects": len(rows), "candidates": candidates}

        raise ValueError("فرمت نقشه پشتیبانی نمی‌شود؛ PDF، DWG، DXF یا IFC انتخاب کنید.")

    def review_candidates(self, inspection, confirmations=None, *, reviewer="local-user", reviewed_at=None):
        accepted, audit = review_candidates(
            inspection.get("candidates", []) or [],
            confirmations,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        self.last_review_audit = audit
        return accepted, audit

    def candidates_to_rows(self, inspection, confirmations=None):
        accepted, _audit = self.review_candidates(inspection, confirmations)
        out = []
        seen_sources = set()
        for row in accepted:
            source = str(row.get("source") or "").strip()
            if not source:
                raise ValueError("drawing candidate source is required")
            if source in seen_sources:
                raise ValueError(f"منبع متره تکراری و مستعد دوباره‌شماری: {source}")
            seen_sources.add(source)
            quantity = float(row.get("quantity", 0) or 0)
            if not math.isfinite(quantity) or quantity < 0:
                raise ValueError("drawing quantity must be finite and non-negative")
            result = {
                "source": source,
                "description": row.get("description", ""),
                "quantity": quantity,
                "unit": row.get("unit", ""),
                "needs_confirmation": bool(row.get("needs_confirmation", False)),
                "confirmation_status": row.get("confirmation_status", "approved"),
                "confirmed_by": row.get("confirmed_by", ""),
                "confirmed_at": row.get("confirmed_at", ""),
                "provenance": dict(row.get("provenance") or {}),
            }
            for key in (
                "confidence", "recognition_confidence", "recognition_reason",
                "element_type", "entity_type", "layer", "handle", "metric",
                "page", "sheet", "sheet_id", "revision", "duplicate_geometry",
                "duplicate_of", "partial_overlap", "overlap_sources", "overlap_length",
                "scale_status", "scale", "scale_candidates",
                "opening_quantity", "net_quantity", "opening_exceeds_gross", "opening_error",
            ):
                if key in row:
                    result[key] = row[key]
            out.append(result)
        return out
