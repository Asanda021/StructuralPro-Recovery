# StructuralPro — Authoritative Project Handoff

**Repository:** Asanda021/StructuralPro  
**Baseline Main:** 612542e2619cd171418b1025db2c3f64253755b4  
**Product state:** Product Acceptance / Maintenance / Versioned Feature Development

## Non-negotiable engineering rules

- Preserve the existing architecture; no rewrite.
- No parallel modules or duplicate business logic.
- No fake production behavior or fake-green CI.
- Never delete tests to make CI pass.
- Never guess drawing scale, quantities, engineering values, or official/market prices.
- Keep fail-closed behavior where validation/calibration/provider evidence is insufficient.
- StructuralPro must remain fully separated from StructuralBot: no data, module, API, model, or dependency coupling.
- Before changing code: inspect the existing implementation, identify the responsible service/module, reuse existing handlers/services, make the smallest justified change, run targeted tests and regression, verify GitHub Actions, then report.
- Do not create new mandatory roadmap phases (P81/P82/etc.). Future work is a Feature/Version Update or a targeted defect fix.

## Product scope

StructuralPro is a Windows-first professional AEC product covering:

Architecture; Structural Concrete; Structural Steel; Masonry; Timber; Composite; Mechanical; Electrical; Plumbing; Renovation; Historic; Site/External; BIM/IFC; PDF/CAD; Quantity Takeoff; BOQ; Pricebook; Factors; Estimate; Statement; Reports; Documents; Cost Control; Collaboration; Local AI.

ETABS/SAFE integration is outside the current StructuralPro architecture.

## Primary workflow

**Project → Drawing/Takeoff → Items → Pricebook → Factors → BOQ → Estimate → Statement → Reports**

Do not create a parallel workflow.

## UI baseline

The authoritative Windows UI baseline is PR #415/#416:

- Top horizontal navigation
- RTL / Persian-friendly labels
- Project-first dashboard
- Contextual command ribbon
- Controlled Glass/Acrylic styling
- Professional Windows desktop presentation
- Soft hover/transition behavior
- No clutter or developer-oriented presentation

## CAD / PDF

### DWG

Required boundary:

**DWG → Provider → Converter → DXF → ezdxf → Extraction → Takeoff**

Native DWG parsing is forbidden. Missing/invalid provider capability must fail closed.

### DXF

Use real ezdxf parsing. Supported production entities include:

LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, TEXT, MTEXT, INSERT/BLOCK, HATCH.

Unit normalization is required.

### PDF

Use PyMuPDF. Vector evidence is required. Never guess scale. Invalid calibration must fail closed.

## Pricebook

Supported user import formats:

- XLSX
- XLSM
- CSV

Requirements:

- Persian/English headers
- Validation
- Fail-closed invalid input
- SHA-256 provenance
- Existing persistence: ~/.structuralpro/pricebook_user.csv
- No fake official or market prices

## AEC discipline mapping

Canonical → operational:

- architecture → building
- structural_concrete → building
- structural_steel → advanced
- masonry → building
- timber → advanced
- composite → advanced
- mechanical → mechanical
- electrical → electrical
- renovation → advanced
- historic → advanced
- site_external → civil

Legacy operational domains remain supported:

- building
- mechanical
- electrical
- civil
- advanced

Do not change this mapping unless an actual TakeoffEngine failure is demonstrated.

## AI

AI is local/offline through llama.cpp and assists the workflow; deterministic engineering calculations remain authoritative.

- Standard: Qwen2.5-0.5B Q4_K_M
- Pro/Enterprise: Qwen2.5-VL-3B Q4_K_M + mmproj

AI must not generate authoritative engineering quantities or values.

## Windows editions

- Light
- Standard
- Pro
- Enterprise

Edition behavior is defined by core/platform/product.py.

Packaging:

packaging/build_windows_edition.ps1

Installer:

packaging/installer-edition.iss

Edition runtime and packaged capabilities must remain consistent with the edition matrix.

## Acceptance / CI

PR #417 completed Product Workflow Acceptance Gates 1–4 and was merged as:

612542e2619cd171418b1025db2c3f64253755b4

Validated workflow:

Project → Takeoff/Items → Pricebook → Factors → BOQ → Estimate → Statement → Reports → Persistence/Integrity.

Full relevant test workflow:

Run 37805020701 — SUCCESS.

Historical/stale runs are not a substitute for current evidence. Reports must distinguish current gating evidence from historical/non-gating runs.

## Post-merge verification policy

After a merge, verification should cover, where the relevant workflows exist:

1. Main branch state
2. Windows smoke
3. Windows release/package validation
4. Full AEC workflow
5. CI gating
6. Fail-closed behavior
7. UI navigation / Glass-Acrylic regression

Completion must be declared only from real GitHub evidence.

## Current state

- Architecture stable
- AEC registry stable
- Takeoff/BOQ/Estimate validated
- Pricebook validated
- Factors validated
- Statement validated
- Reports validated
- Persistence validated
- CAD/PDF validated
- Real DXF parsing validated
- DWG fail-closed boundary validated
- Licensing validated
- Windows editions built
- Local AI integrated
- UI navigation corrected
- Dashboard corrected
- Glass/Acrylic integrated
- Acceptance Gates 1–4 completed
- PR #417 merged

This document is a governance/handoff baseline. It does not introduce a new roadmap phase and does not authorize architectural rewrites.
