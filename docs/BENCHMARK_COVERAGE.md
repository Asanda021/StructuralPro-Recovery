# StructuralPro — Benchmark Coverage

StructuralPro targets full coverage of relevant, transferable capabilities found
in quantity-takeoff, estimating and construction-platform products.

## Benchmark scope

The benchmark surface covers:

- CAD/DWG/DXF intake and geometry extraction
- 2D takeoff: length, area, count, perimeter, volume, formulas, cutouts
- drawing scale, units, layers, blocks, Xrefs and viewports
- visual search, dynamic fill and local-AI-assisted counting/mapping
- drawing revision compare/overlay and quantity deltas
- IFC/BIM intake, object classification, quantities and 2D/3D linkage
- project templates, library, packages, backup, audit and readiness
- members, roles, comments and approval contracts
- offline-first sync and optional cloud synchronization
- annual price lists, search, import/export, price analysis and resource library
- price snapshots, indexation and official-dataset import pipeline
- BOQ, assemblies, factors, transport, cost breakdown and estimate history
- statements, cumulative quantities, retention/deductions, finalization and financial summaries
- PDF, Excel, Word, CSV and custom reports
- Excel/API/project-transfer/CAD-to-BOQ integration contracts
- local AI assistant, missing-input detection and quantity QA
- licensing, Windows, Android and Telegram client contracts
- RTL UX, shortcuts and ready-made inputs
- structural, architectural, mechanical, electrical and civil domains
- MEP coordination and document/drawing cross-links

## Completion rule

A capability is **not** considered fully implemented merely because its name
exists in a registry. It must have an executable handler or a tested integration
adapter. External proprietary formats are supported only through a real adapter.

The final acceptance gate will therefore report three numbers:

1. **Implemented** — executable functionality is wired.
2. **Contract** — stable API/interface exists, but an external adapter or client is still required.
3. **Planned** — no implementation yet.

This prevents a false "100%" claim while the product is still being built.

## Product rule

The deterministic quantity/estimating engine remains authoritative. Local AI can
assist with classification, QA, suggestions and document interpretation, but it
does not silently replace engineering calculations.

Core calculation and local AI remain offline-first. Internet is optional for
sync, backup, updates and other cloud features.
