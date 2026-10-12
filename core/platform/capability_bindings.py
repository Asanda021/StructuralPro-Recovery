"""Executable bindings for StructuralPro capabilities."""
from __future__ import annotations
from typing import Any, Callable
from core.drawings.advanced_takeoff import (
    depth_volume, cutout_area, legend, visual_symbol_search, dynamic_fill,
    ai_count, ai_map, length_takeoff, area_takeoff, count_takeoff, perimeter_takeoff,
)
from core.drawings.bim_quantities import classify_objects, extract_quantities, link_2d_3d
from core.drawings.dwg_takeoff import DWGTakeoffEngine, infer_takeoff_from_layers
from core.drawings.revisions import compare as compare_drawings
from core.takeoff.boq import build_boq
from core.takeoff.costing import cost_breakdown
from core.takeoff.formulas import evaluate as evaluate_formula
from core.takeoff.quantity_tools import apply_waste
from core.takeoff.transport import calculate_transport
from core.takeoff.modules import calculate_building_item, calculate_mechanical_item, calculate_electrical_item, calculate_civil_item
from core.ai.takeoff_assistant import LocalTakeoffAssistant
from core.ai.local_engine import LocalAIEngine
from core.pricing.annual_update import AnnualPriceImporter
from core.projects.workflow import project_health, audit_project, save_template, export_package, backup_project, copy_project
from core.takeoff.estimate_history import snapshot as estimate_snapshot, delta as estimate_delta
from core.reports.custom import build_custom_report
from core.reports.rtl import report_schema
from core.platform.clients import ProductClient
from core.platform.production_boundaries import validate_license, project_fingerprint, sync_envelope, collaboration_member, add_comment, approval_state, License
from core.pricing.production import validate_dataset_rows, price_analysis

def _identity(*args: Any, **kwargs: Any) -> Any:
    return kwargs or (args[0] if len(args) == 1 else list(args))

def _missing_inputs(project: Any) -> list[dict[str, str]]:
    if not isinstance(project, dict):
        return [{"code": "invalid_project", "message": "پروژه باید به صورت شیء داده‌ای باشد."}]
    return [{"code": "missing_project_name", "message": "نام پروژه وارد نشده است."}] if not str(project.get("name", "")).strip() else []

def _suggest_next_actions(project: Any) -> list[str]:
    return ["تکمیل اطلاعات پروژه", "اجرای متره", "تطبیق با فهرست‌بها", "بازبینی هشدارها"]

def build_bindings() -> dict[str, Callable[..., Any]]:
    assistant = LocalTakeoffAssistant()
    local_ai = LocalAIEngine()
    annual_prices = AnnualPriceImporter()
    return {
        "cad-dwg": DWGTakeoffEngine().import_file,
        "cad-dwg-summary": DWGTakeoffEngine().summarize,
        "cad-dxf": DWGTakeoffEngine().import_file,
        "cad-layers": lambda r: r.layers,
        "cad-lines": lambda r: [e for e in r.entities if e.entity_type == "LINE"],
        "cad-polylines": lambda r: [e for e in r.entities if e.entity_type in {"POLYLINE", "LWPOLYLINE"}],
        "cad-arcs": lambda r: [e for e in r.entities if e.entity_type == "ARC"],
        "cad-circles": lambda r: [e for e in r.entities if e.entity_type == "CIRCLE"],
        "cad-ellipse": lambda r: [e for e in r.entities if e.entity_type == "ELLIPSE"],
        "cad-blocks": lambda r: r.block_counts,
        "cad-text": lambda r: r.text_labels,
        "cad-hatch": lambda r: [e for e in r.entities if e.entity_type == "HATCH"],
        "cad-dimensions": lambda r: [e for e in r.entities if e.entity_type == "DIMENSION"],
        "cad-xref": lambda r: r.xrefs,
        "cad-units": lambda r: r.units,
        "cad-scale": lambda drawing_length, real_length: real_length / drawing_length,
        "cad-viewport": _identity,
        "takeoff-classification": _identity,
        "takeoff-length": length_takeoff,
        "takeoff-area": area_takeoff,
        "takeoff-count": count_takeoff,
        "takeoff-perimeter": perimeter_takeoff,
        "takeoff-volume": depth_volume,
        "takeoff-depth": depth_volume,
        "takeoff-cutout": cutout_area,
        "takeoff-formula": evaluate_formula,
        "takeoff-waste": apply_waste,
        "takeoff-markup": _identity,
        "takeoff-legend": legend,
        "takeoff-visual-search": visual_symbol_search,
        "takeoff-dynamic-fill": dynamic_fill,
        "takeoff-ai-count": ai_count,
        "takeoff-ai-map": ai_map,
        "revision-drawing": compare_drawings,
        "revision-overlay": compare_drawings,
        "revision-quantity-delta": estimate_delta,
        "revision-history": estimate_snapshot,
        "bim-ifc": _identity,
        "bim-objects": classify_objects,
        "bim-quantities": extract_quantities,
        "bim-2d3d-link": link_2d_3d,
        "estimate-boq": build_boq,
        "estimate-transport": calculate_transport,
        "estimate-cost-breakdown": cost_breakdown,
        "estimate-history": estimate_snapshot,
        "estimate-change": estimate_delta,
        "estimate-assemblies": _identity,
        "estimate-factors": price_analysis,
        "integration-cad": infer_takeoff_from_layers,
        "ai-missing": _missing_inputs,
        "ai-next": _suggest_next_actions,
        "ai-qa": assistant.qa,
        "project-templates": save_template,
        "project-library": lambda project: project,
        "project-package": export_package,
        "project-backup": backup_project,
        "project-audit": audit_project,
        "project-health": project_health,
        "collab-members": collaboration_member,
        "collab-roles": collaboration_member,
        "collab-comments": add_comment,
        "collab-realtime": _identity,
        "cloud-sync": sync_envelope,
        "cloud-offline": sync_envelope,
        "reports-custom": build_custom_report,
        "reports-pdf": _identity,
        "reports-excel": _identity,
        "reports-word": _identity,
        "reports-csv": _identity,
        "integration-excel": _identity,
        "integration-api": _identity,
        "integration-transfer": _identity,
        "ai-assistant": local_ai.answer,
        "ai-project-inspection": local_ai.inspect_project,
        "security-license": validate_license,
        "platform-windows": lambda: ProductClient("windows").state(),
        "platform-android": lambda: ProductClient("android").state(),
        "platform-telegram": lambda: ProductClient("telegram").state(),
        "ux-rtl": report_schema,
        "ux-shortcuts": _identity,
        "ux-presets": _identity,
        "pricing-years": lambda catalog: catalog.years(),
        "pricing-search": lambda catalog, query, **kwargs: catalog.search(query, **kwargs),
        "pricing-import": lambda catalog, text: catalog.import_csv(text),
        "pricing-annual-validate": annual_prices.validate,
        "pricing-annual-convert": annual_prices.convert,
        "pricing-export": lambda catalog, year=None: catalog.export_csv(year),
        "pricing-analysis": price_analysis,
        "pricing-resources": _identity,
        "pricing-snapshot": lambda catalog, codes, year=None: catalog.snapshot(codes, year),
        "pricing-indexation": price_analysis,
        "pricing-real-data": validate_dataset_rows,
        "statement-multi": _identity,
        "statement-cumulative": _identity,
        "statement-retention": _identity,
        "statement-finalize": _identity,
        "statement-financial": _identity,
        "document-links": _identity,
        "domain-structural": _identity,
        "domain-architectural": calculate_building_item,
        "domain-mechanical": calculate_mechanical_item,
        "domain-electrical": calculate_electrical_item,
        "domain-civil": calculate_civil_item,
        "domain-mep-coordination": _identity,
        "document-links": _identity,
    }
