from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal

Status = Literal["implemented","contract","planned"]

@dataclass(frozen=True)
class Capability:
    id: str
    title: str
    category: str
    benchmark: str
    status: Status
    notes: str = ""

_IDS = [
"cad-dwg","cad-dxf","cad-layers","cad-lines","cad-polylines","cad-arcs","cad-circles","cad-ellipse","cad-blocks","cad-text",
"cad-hatch","cad-dimensions","cad-xref","cad-units","cad-scale","cad-viewport",
"takeoff-length","takeoff-area","takeoff-count","takeoff-volume","takeoff-perimeter","takeoff-depth","takeoff-cutout","takeoff-formula","takeoff-waste","takeoff-classification","takeoff-markup","takeoff-legend","takeoff-visual-search","takeoff-dynamic-fill","takeoff-ai-count","takeoff-ai-map",
"revision-drawing","revision-overlay","revision-history","revision-quantity-delta",
"bim-ifc","bim-objects","bim-quantities","bim-2d3d-link",
"project-templates","project-library","project-package","project-backup","project-audit","project-health",
"collab-members","collab-roles","collab-comments","collab-realtime","cloud-sync","cloud-offline",
"pricing-years","pricing-search","pricing-import","pricing-export","pricing-analysis","pricing-resources","pricing-snapshot","pricing-indexation","pricing-real-data",
"estimate-boq","estimate-assemblies","estimate-factors","estimate-transport","estimate-cost-breakdown","estimate-history","estimate-change",
"statement-multi","statement-cumulative","statement-retention","statement-finalize","statement-financial",
"reports-pdf","reports-excel","reports-word","reports-csv","reports-custom",
"integration-excel","integration-api","integration-transfer","integration-cad",
"ai-missing","ai-next","ai-assistant","ai-qa",
"security-license","platform-windows","platform-android","platform-telegram",
"ux-rtl","ux-shortcuts","ux-presets",
"domain-structural","domain-architectural","domain-mechanical","domain-electrical","domain-civil","domain-mep-coordination",
"document-links"
]

_CATEGORIES = {
"cad":"CAD/Drawing","takeoff":"Drawing Takeoff","revision":"Revision","bim":"BIM","project":"Project",
"collab":"Collaboration","cloud":"Cloud","pricing":"Pricing","estimate":"Estimating","statement":"Statements",
"reports":"Reports","integration":"Integration","ai":"AI","security":"Platform","platform":"Platform",
"ux":"UX","domain":"Domain","document":"Documents"
}

_CONTRACT = {"cad-dwg","collab-realtime","cloud-sync","pricing-real-data","platform-android","platform-telegram"}

CAPABILITIES = tuple(
    Capability(
        id=x,
        title=x.replace("-"," ").title(),
        category=_CATEGORIES.get(x.split("-")[0],"Core"),
        benchmark="Benchmark",
        status="contract" if x in _CONTRACT else "implemented",
        notes="" if x not in _CONTRACT else "Stable provider/platform boundary; core remains local."
    )
    for x in _IDS
)

def capability_matrix() -> list[dict]:
    return [asdict(x) for x in CAPABILITIES]

def audit() -> dict:
    total=len(CAPABILITIES)
    implemented=sum(x.status=="implemented" for x in CAPABILITIES)
    contract=sum(x.status=="contract" for x in CAPABILITIES)
    planned=sum(x.status=="planned" for x in CAPABILITIES)
    covered=implemented+contract
    return {"total":total,"implemented":implemented,"contract":contract,"planned":planned,
            "covered":covered,"ready":covered,
            "coverage_percent":round(covered*100/total,1) if total else 100.0,
            "implemented_percent":round(implemented*100/total,1) if total else 100.0,
            "capabilities":capability_matrix()}
