"""Phase 19 — Drawing Intelligence orchestration.

Connects source adapters, sheet/scale/zone recognition, explicit dimensions,
engineering-element recognition and measured geometry into auditable quantity
links. No missing engineering value is inferred; unresolved data remains a
warning and quantities are not fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters import DrawingAdapterRegistry, AdapterResult
from .intelligence_v2 import DrawingIntelligenceV2, SheetIdentity, ScaleEvidence
from .production_v1 import DrawingProductionWorkflow, DimensionEvidence, ZoneIdentity
from .measurement import DrawingScale, primitive_measurements, scale_from_metadata
from .models import EngineeringElement


@dataclass(frozen=True)
class MeasurementLink:
    measurement_source_id: str
    element_id: str
    quantity: float
    unit: str
    boq_key: str
    confidence: float
    evidence: tuple[str, ...] = ()

    def validate(self) -> "MeasurementLink":
        if not self.measurement_source_id.strip() or not self.element_id.strip():
            raise ValueError("measurement and element identities are required")
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if not self.unit.strip() or not self.boq_key.strip():
            raise ValueError("unit and boq_key are required")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return self


@dataclass(frozen=True)
class DrawingIntelligenceResult:
    source: Any
    adapter_warnings: tuple[str, ...]
    sheets: tuple[SheetIdentity, ...]
    scale: DrawingScale | None
    scale_evidence: ScaleEvidence
    dimensions: tuple[DimensionEvidence, ...]
    zones: tuple[ZoneIdentity, ...]
    elements: tuple[EngineeringElement, ...]
    measurements: tuple[dict[str, Any], ...]
    measurement_links: tuple[MeasurementLink, ...]
    warnings: tuple[str, ...]


class DrawingIntelligenceWorkflow:
    """Fail-closed P19 drawing-to-quantity intelligence boundary."""

    def __init__(self, adapters: DrawingAdapterRegistry | None = None):
        self.adapters = adapters or DrawingAdapterRegistry()
        self.intelligence = DrawingIntelligenceV2()
        self.production = DrawingProductionWorkflow()

    @staticmethod
    def _boq_key(element: EngineeringElement) -> str:
        return f"{element.domain}:{element.kind}:{element.element_id}"

    @staticmethod
    def _measurement_index(measurements):
        return {
            sid: m
            for m in measurements
            for sid in m.get("source_ids", ())
            if sid
        }

    def analyze(
        self,
        path: str,
        *,
        unit: str | None = None,
        scale_denominator: float | None = None,
    ) -> DrawingIntelligenceResult:
        adapted: AdapterResult = self.adapters.read(path)
        primitives = self.intelligence.suppress_duplicates(adapted.primitives)

        sheets = self.intelligence.detect_sheets(primitives)
        scale_evidence = self.intelligence.infer_scale(
            primitives,
            {
                "scale_denominator": scale_denominator,
            } if scale_denominator is not None else adapted.source.metadata,
        )

        scale = None
        warnings = list(adapted.warnings)
        if unit is not None:
            try:
                if scale_denominator is None:
                    raise ValueError("scale_denominator is required when unit is supplied")
                scale = __import__("core.drawing.measurement", fromlist=["scale_from_unit"]).scale_from_unit(
                    unit, scale_denominator, "explicit-input"
                )
            except (TypeError, ValueError) as exc:
                warnings.append(f"scale rejected: {exc}")
        elif scale_evidence.denominator is not None:
            source = scale_evidence.source_id or "drawing-intelligence"
            try:
                drawing_unit = adapted.source.metadata.get("unit") or adapted.source.metadata.get("units")
                if not isinstance(drawing_unit, str) or not drawing_unit.strip():
                    raise ValueError("drawing unit is missing; scale cannot be converted to engineering units")
                scale = scale_from_metadata(
                    {
                        "unit": drawing_unit,
                        "scale_denominator": scale_evidence.denominator,
                    }
                )
                if scale is None:
                    raise ValueError("drawing unit/scale metadata is incomplete")
                scale = DrawingScale(scale.unit, scale.factor_to_m, scale.scale_denominator, source)
            except (TypeError, ValueError) as exc:
                warnings.append(f"scale unresolved: {exc}")

        dimensions = self.production.extract_dimensions(primitives)
        zones = self.production.infer_zones(primitives, sheets)
        elements = self.production.recognize_elements(primitives)

        measurements = ()
        links = []
        if scale is not None:
            measurements = tuple(
                {
                    "value": m.value,
                    "unit": m.unit,
                    "source_ids": m.source_ids,
                    "formula": m.formula,
                    "warnings": m.warnings,
                }
                for m in primitive_measurements(primitives, scale)
            )
            measurement_index = self._measurement_index(measurements)
            element_by_source = {
                sid: element
                for element in elements
                for sid in element.source_ids
                if sid
            }
            for source_id, measurement in measurement_index.items():
                element = element_by_source.get(source_id)
                if element is None:
                    continue
                links.append(
                    MeasurementLink(
                        measurement_source_id=source_id,
                        element_id=element.element_id,
                        quantity=float(measurement["value"]),
                        unit=str(measurement["unit"]),
                        boq_key=self._boq_key(element),
                        confidence=element.confidence,
                        evidence=("source-id measurement↔element linkage",),
                    ).validate()
                )
        else:
            warnings.append("measurement-to-BOQ linkage blocked because scale is unresolved")

        return DrawingIntelligenceResult(
            source=adapted.source,
            adapter_warnings=adapted.warnings,
            sheets=sheets,
            scale=scale,
            scale_evidence=scale_evidence,
            dimensions=dimensions,
            zones=zones,
            elements=elements,
            measurements=measurements,
            measurement_links=tuple(links),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @staticmethod
    def export(result: DrawingIntelligenceResult) -> dict[str, Any]:
        return {
            "source": str(result.source.path),
            "kind": result.source.kind,
            "sheets": [
                {
                    "sheet_id": s.sheet_id,
                    "page": s.page,
                    "title": s.title,
                    "confidence": s.confidence,
                    "evidence": s.evidence,
                }
                for s in result.sheets
            ],
            "scale": None if result.scale is None else {
                "unit": result.scale.unit,
                "factor_to_m": result.scale.factor_to_m,
                "scale_denominator": result.scale.scale_denominator,
                "source": result.scale.source,
            },
            "scale_evidence": {
                "denominator": result.scale_evidence.denominator,
                "confidence": result.scale_evidence.confidence,
                "source_id": result.scale_evidence.source_id,
                "reason": result.scale_evidence.reason,
            },
            "dimensions": [
                {
                    "value": d.value,
                    "source_id": d.source_id,
                    "unit": d.unit,
                    "confidence": d.confidence,
                    "evidence": d.evidence,
                }
                for d in result.dimensions
            ],
            "zones": [
                {
                    "key": z.key,
                    "source_ids": z.source_ids,
                    "sheet_ids": z.sheet_ids,
                    "confidence": z.confidence,
                }
                for z in result.zones
            ],
            "elements": [
                {
                    "element_id": e.element_id,
                    "domain": e.domain,
                    "kind": e.kind,
                    "source_ids": e.source_ids,
                    "confidence": e.confidence,
                }
                for e in result.elements
            ],
            "measurements": list(result.measurements),
            "measurement_links": [
                {
                    "measurement_source_id": x.measurement_source_id,
                    "element_id": x.element_id,
                    "quantity": x.quantity,
                    "unit": x.unit,
                    "boq_key": x.boq_key,
                    "confidence": x.confidence,
                    "evidence": x.evidence,
                }
                for x in result.measurement_links
            ],
            "warnings": result.warnings,
        }
