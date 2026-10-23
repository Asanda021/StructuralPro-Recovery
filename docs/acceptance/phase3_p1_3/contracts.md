# Phase 3 priorities 1–3: supported contract

All fixtures in this directory are synthetic software evidence, never an official pricebook, customer design, engineering signature or payment authorization.

## Existing paths retained

`rebuild_project_boq` remains the only quantity projection. `effective_takeoffs` supplies applied manual, drawing, roof and IFC amendments/ownership transfers. Original takeoffs remain unchanged. `audit_boq` reconciles the effective source/operation/unit groups exactly; BOQ source IDs link back to floor/member/geometry/SHA/review records in the project. No new SQL schema or calculation engine was added.

The price mapping command operates on current BOQ indices under an expected project digest. It verifies source-file rates and compatible units, uses only imported rates, records source IDs/code/reviewer/file hash, and does not change engineering quantities. A later quantity rebuild requires reconciliation/review again; it cannot silently authorize a new price. Failed mapping writes nothing.

## Pricebooks

Text CSV and actual openpyxl XLSX/XLSM import retain the existing import service. Empty Excel rows are ignored; nonempty incomplete rows and duplicate semantic headers fail closed. Long Excel numeric cells remain rejected where their source digits cannot be recovered. Source filename/hash/year/format/import time remain in the receipt. New GUI project bindings require explicit IRR or IRT and source version; no currency conversion occurs. Historical bindings without those additions remain historical preview inputs. An approved binding cannot be replaced through the new command without explicit replacement permission; the former snapshot remains in history. Financial locks are still enforced by ProjectStore.

PDF pricebook extraction remains limited to the existing text extraction contract; this mission makes no new PDF/OCR pricebook claim.

## Factors and exact estimates

The existing Decimal contract (128-digit input/exponent bounds, 512-digit trapped calculation context, lossless JSON wire encoding) remains authoritative. Exact means retained digits, not quantization to an inferred monetary unit. There is no hidden money rounding or IRR/IRT conversion.

Reviewed factor evidence is a user-provided JSON document with explicit version, year, currency, ISO effective date, `basis: sequential_compound`, and an ordered list of `{name, rate}` entries. Author/reviewer must be different nonblank identities. Rates on this cost-engine path are finite, nonnegative and explicit; no unknown contractual formula is inferred. The legacy FactorRegistry retains its documented discount range down to -1, with exact digits and boolean rejection. A registry discount is not automatically a supported reviewed estimate factor.

The document hash, data and ordered rates are rechecked before recalculation. Reopening sorted-key SQLite JSON cannot reorder the document's factor list. Existing estimates are retained in `estimate_history`; original SQLite revisions also remain available. Bare legacy factor calculations remain previews under the existing financial-policy status, not newly authorized payments.

Estimate comparison preserves exact deltas and distinguishes multiple physical sources carrying the same operation/price code. Unpriced estimates can be quantity-valid but cannot be financially finalized.

## Test evolution

The old real UI finance probe now supplies the newly required currency/version; all its former outcome assertions remain. The golden unpriced quantity test retains geometry and BOQ validity checks and additionally asserts financial finalization is blocked. No test was deleted or skipped to conceal a failure.

The diagnostic full run was not final acceptance: 7718 passed, 2 failed, 5 PowerShell skips, Exit 1. It exposed the old UI inputs and the obsolete unpriced finalization expectation. Product changes made during that diagnostic run mean it is not evidence for the final tree. The final full run is recorded separately.

## Five-floor independent oracle

Five floors exist, with active work on L1/L2. A real vector PDF binds a 4 m × 4 m solid slab. A documented thickness amendment changes concrete from 3.2 to 4 m³ while retaining original takeoffs. Formwork is explicitly 16 m²; two documented reinforcement schedules total 71.04 kg. A manually sourced 5 m × 3 m wall minus 2 m² openings gives 13 m². Synthetic imported rates are 100, 20, 10 and 50 IRR respectively. Base = 2080.40 IRR. Explicit sequential rates 0.1 and 0.05 produce 2402.86200 IRR. These are test numbers, not real market rates.

The existing PDF/XLSX/DOCX/CSV report paths produce files which are reopened structurally. Native Microsoft Office/Windows acceptance is not claimed. The 100,000-entity CAD gate remains 500 ms and unchanged.
