# StructuralPro — Phase 15 Competitive Benchmark Baseline

## Purpose

Phase 15 freezes the competitive baseline for StructuralPro before capability-parity implementation begins. It compares the product surface against representative Iranian quantity/estimating workflows and current foreign takeoff/estimating products.

This document is a scope baseline, not a claim that every capability is already implemented.

## Status vocabulary
- implemented — executable StructuralPro capability is already present and tested.
- contract — a stable interface/adapter exists, but an external runtime, converter, dataset, or client is still required.
- roadmap — capability is assigned to a later mandatory roadmap phase.
- benchmark-only — competitor capability is useful as a comparison point but is not independently required unless covered by the mapped phase.

No capability is left unclassified.

## Benchmark matrix

| ID | Capability | Iranian parity | Foreign benchmark | StructuralPro baseline | Mandatory phase |
|---|---|---|---|---|---|
| B01 | ریزمتره و خلاصه متره | required | takeoff reports | roadmap | P16 |
| B02 | BOQ / آیتم‌بندی / واحدها | required | bid/estimate items | roadmap | P16 |
| B03 | فهرست‌بها و نسخه قیمت | required | pricing libraries | roadmap | P16 |
| B04 | ضرایب و آنالیز بها | required | assemblies/formulas | roadmap | P16/P24 |
| B05 | صورت‌وضعیت و تجمعی | required | commercial workflows | roadmap | P17 |
| B06 | کسورات/تعدیلات مالی | required | commercial controls | roadmap | P17 |
| B07 | PDF viewer and measurement | expected | PlanSwift/Bluebeam | roadmap | P18 |
| B08 | length/area/volume/count/perimeter | required | PlanSwift/Bluebeam | roadmap | P18 |
| B09 | scale, units, calibration | required | Auto Scale / scale calibration | roadmap | P18 |
| B10 | cutout/crop/markup/annotation | useful | PlanSwift/Bluebeam | roadmap | P18 |
| B11 | measurement history + undo/redo | expected | modern takeoff UX | roadmap | P18/P28 |
| B12 | drawing/sheet detection | advanced | AI takeoff tools | roadmap | P19 |
| B13 | measurement-to-BOQ linkage | required | integrated takeoff/estimate | roadmap | P19/P24 |
| B14 | revision overlay/compare | required | PlanSwift revision comparison | roadmap | P20 |
| B15 | revision quantity delta | advanced | revision-aware estimating | roadmap | P20 |
| B16 | DWG/DXF import | required | PlanSwift/CAD workflows | roadmap | P21 |
| B17 | layers/blocks/polylines/dimensions/text | required | CAD takeoff | roadmap | P21 |
| B18 | CAD-to-takeoff/BOQ | advanced | CAD estimating workflows | roadmap | P21 |
| B19 | IFC import and property extraction | advanced | Autodesk Takeoff/BIM | roadmap | P22 |
| B20 | BIM quantity extraction | advanced | Autodesk Takeoff/BIM | roadmap | P22 |
| B21 | 2D/3D element linkage | advanced | BIM takeoff | roadmap | P22 |
| B22 | model revision/change impact | advanced | BIM revision workflows | roadmap | P22 |
| B23 | AI auto takeoff | advanced | PlanSwift Takeoff BOOST | roadmap | P23 |
| B24 | AI auto count | advanced | PlanSwift Auto Count | roadmap | P23 |
| B25 | AI auto scale | advanced | PlanSwift Auto Scale | roadmap | P23 |
| B26 | AI confidence + human approval | required safety pattern | current AI takeoff workflows | roadmap | P23 |
| B27 | assemblies/material/labor/waste | required | PlanSwift estimating | roadmap | P24 |
| B28 | custom formulas/templates | required | PlanSwift custom formulas/templates | roadmap | P24 |
| B29 | scenarios/alternatives | useful | estimating platforms | roadmap | P24 |
| B30 | multi-user roles/permissions | expected | collaborative platforms | roadmap | P25 |
| B31 | comments/review/approval | expected | collaborative platforms | roadmap | P25 |
| B32 | audit trail/change history | required | professional estimating workflows | roadmap | P25 |
| B33 | professional PDF/Excel reports | required | PlanSwift/Bluebeam reporting | roadmap | P26 |
| B34 | Word/CSV/custom reporting | useful | reporting ecosystems | roadmap | P26 |
| B35 | RTL/Persian terminology quality | critical for Iran | localization quality | roadmap | P27 |
| B36 | keyboard shortcuts/quick actions | expected | professional desktop UX | roadmap | P28 |
| B37 | drag/drop/context/bulk actions | expected | professional desktop UX | roadmap | P28 |
| B38 | accessibility/responsive/performance UX | expected | modern desktop/web UX | roadmap | P28 |
| B39 | real-project quantity validation | critical | professional estimating QA | roadmap | P29 |
| B40 | large PDF/CAD/BIM performance | critical | production takeoff tools | roadmap | P30 |
| B41 | backup/restore/migration | required | project platforms | roadmap | P30/P31 |
| B42 | licensing/trial/update/onboarding | commercial | commercial products | roadmap | P31 |
| B43 | full regression | mandatory | release engineering | roadmap | P32 |
| B44 | final competitive re-benchmark | mandatory | parity gate | roadmap | P33 |
| B45 | final acceptance/sign-off | mandatory | product release gate | roadmap | P34/P35 |

## Competitor capability anchors

### PlanSwift

Current PlanSwift documentation exposes digital takeoff for area, length, count, slope and volume; symbol counting; cutouts; multi-scale plans; plan overlay/comparison; annotations; assemblies; custom formulas/templates; material and labor libraries; Excel integration; and configurable reports. Its current Takeoff BOOST suite adds AI-assisted Auto Takeoff, Auto Count, Auto Scale and Auto Bookmark.

### Bluebeam Revu

Bluebeam documentation covers PDF takeoff measurements such as length, area, volume, perimeter and count, with custom columns and Excel Quantity Link workflows.

### Autodesk Takeoff / BIM benchmark

Autodesk Takeoff remains a benchmark target for integrated 2D/3D/BIM takeoff and model-aware quantity workflows. This is represented by the BIM and drawing-intelligence rows above rather than by treating a viewer alone as sufficient.

### Iranian benchmark

Iranian professional workflows are represented by the mandatory P16/P17 scope: فهرست‌بها، ریزمتره، خلاصه متره، BOQ، ضرایب، آنالیز بها، صورت‌وضعیت، تجمعی، کسورات و گزارش‌های مالی/فنی. The baseline intentionally treats these as first-class product requirements, not optional localization.

## Baseline decision

Phase 15 is complete when:
1. every benchmark capability has a unique ID;
2. every capability is classified;
3. every required capability is mapped to a mandatory implementation phase;
4. no benchmark row is orphaned;
5. later phases cannot silently omit a capability from this matrix.

Any new capability discovered after this freeze is treated as a user-requested future feature/version, unless it is required to satisfy an already-listed row or a Phase 33 final re-benchmark gate.

## Relationship to implementation

The repository's existing BENCHMARK_COVERAGE.md remains the implementation-coverage rule: a named capability is not considered implemented merely because a registry entry exists; executable handlers or tested adapters are required.

Phase 15 therefore freezes what must be covered. Phases 16–35 implement, validate and release that scope. Phase 35 is the final implementation + tests + CI + merge + post-merge + competitive verification sign-off gate.