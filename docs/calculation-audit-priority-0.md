# Calculation Audit — Priority 0 / Phase 1

## Purpose
Track deterministic takeoff formula correctness, input validation, coverage, and unresolved discipline-specific review. This is an audit register, not a declaration that all formulas are professionally certified.

## Status definitions
- **Green**: formula reviewed against a defined reference case, boundaries validated, and regression coverage exists.
- **Yellow**: formula appears deterministic but coverage, geometric assumptions, or independent reference validation is incomplete.
- **Red**: known incorrect behavior or unsafe output; must be fixed before release.
- **White**: quantity depends on drawing/specification inputs not yet supplied.

## First hardening pass (current PR)
| Area | Status | Finding / action |
|---|---|---|
| Numeric inputs across building, advanced, civil, mechanical, electrical and assemblies | Green for non-finite rejection | NaN and ±infinity are now rejected by shared per-module numeric guards; regression tests added. |
| Wall/facade opening deductions | Green for invalid-overrun guard | Openings exceeding gross area now raise an error instead of silently returning zero. |
| Backfill deductions | Green for invalid-overrun guard | Deductions exceeding excavation now raise an error instead of silently returning zero. |
| Hollow-core / U-Boot void deductions | Green for invalid-overrun guard | Void volume exceeding gross slab volume now raises an error instead of silently returning zero. |
| Stair concrete | Yellow | Existing fail-closed behavior requires sloped waist geometry, but risers, landings, and openings remain separate geometry-dependent components. |
| Joist-block / joist-foam roof | Yellow | Explicit joist count is supported; derived edge count and span/layout assumptions require reference-dataset validation. |
| Waffle slab | Yellow | Current spacing-based approximation needs independent reference cases for edge ribs, intersections, and perimeter conditions. |
| Rebar takeoff | White / Yellow | Length × unit weight is only valid when bar schedule/shape, laps, hooks, anchorage and waste assumptions are provided. |
| Foundations, beams, columns, walls, slabs, steel, architecture, MEP, sitework | Yellow pending coverage inventory | Must be validated item-by-item against independently calculated reference examples; existence of a formula is not proof of correctness. |

## Audit gate
Do not claim “Professional Takeoff” or mark the complete calculation audit green until every supported item type has:
1. explicit input schema and units;
2. formula and geometric assumptions visible;
3. valid, invalid, boundary, and multi-count tests;
4. an independent reference quantity (golden dataset);
5. documented missing-input behavior;
6. regression verification on CI and post-merge main.

## Scope of this pass
This PR addresses fail-closed numeric and deduction guards only. It does not certify all formulas or close the full discipline matrix.
