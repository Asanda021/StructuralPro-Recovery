# Layer 2 — Engineering Product Acceptance

Layer 2 is the product path from engineering inputs to usable construction quantities and commercial outputs.

## Repository-implemented scope

1. Engineering domain quantity foundations: concrete, steel, masonry and foundations.
2. Versioned engineering standards registry and provenance.
3. Drawing intelligence and deterministic classification.
4. Drawing source adapters and explicit unit/scale handling.
5. Measurement → takeoff → BOQ integration with fail-closed scale handling.
6. Drawing → BOQ traceability and audit lineage.
7. Construction quantity core with explicit geometry, waste and material formulas.
8. Drawing review/selection and human confirmation boundaries.
9. BIM/IFC model identity, quantities, mapping, revision diff and provenance.
10. BOQ, pricing and estimate professionalization with duplicate/mapping review gates.
11. Iranian data and concrete specialization, including explicit roof coefficients and rebar stock-bar accounting.
12. Professional reports/exports and RTL contracts.
13. Revision intelligence and impact review.
14. Collaboration/concurrency contracts.
15. Review-first AI assistance with deterministic fallback boundaries.
16. Client/platform contracts and offline sync surfaces.
17. Validation and golden regression coverage.

## Acceptance rule

Layer 2 is not declared green by the presence of files alone. The Layer 2 Engineering Product Acceptance workflow must compile the repository and pass the complete Layer 2 test set plus project-pipeline and golden acceptance tests.

## External release dependencies

Repository implementation cannot fabricate external commercial evidence. The following remain release-time dependencies when those capabilities are shipped:

- licensed/verified official Iranian annual price-list datasets;
- a redistributable DWG converter/SDK and its runtime terms;
- IFC backend/runtime availability where native IFC ingestion/export is required;
- a redistributable GGUF model plus license/checksum if a model is bundled;
- Windows signing certificate/procedure if signed distribution is required.

These are explicitly outside the deterministic repository gate.
