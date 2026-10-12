# 100% product acceptance gate

StructuralPro is accepted against its defined product contract only when the
executable core paths below are present and regression-tested. Proprietary
competitor internals are not copied.

## Ten production gates

1. **DWG** — offline converter boundary + DWG→DXF→entity→takeoff path.
2. **Graphical PDF** — local page geometry and deterministic line/polygon measurement.
3. **IFC/BIM** — local object classification, quantities and 2D/3D linking.
4. **Price lists** — versioned/provenance-aware dataset ingestion; no fabricated official prices.
5. **Local AI** — GGUF runtime boundary, model-license/checksum manifest and hardware profiles.
6. **Windows** — shared core service and desktop workflow entry points remain offline-first.
7. **Android/Telegram** — shared client/runtime contracts over the same project model.
8. **Sync/conflicts** — durable offline queue, optional provider, deterministic three-way conflict handling and E2E provider tests.
9. **Reports** — CSV/XLSX/DOCX/PDF export paths with RTL report schema.
10. **Regression** — compile + complete pytest suite + focused drawing/production suite in CI.

## Explicit product boundaries

- Official annual price-list *data* must come from a verified/licensed source; the
  repository provides the ingestion, validation and provenance layer and must not
  invent official prices.
- Native DWG parsing remains offline through an installed converter; StructuralPro
  does not upload drawings to a cloud service.
- Large GGUF weights are not committed to Git. A production installer must bundle
  or install a commercially redistributable model and verify its checksum/license.
- Android and Telegram adapters share the same business/data contract; a polished
  native UI for each platform is a separate packaging/distribution deliverable.
- A green CI result means the defined executable acceptance scope is green; it is
  not a claim that third-party installers, proprietary price datasets, model
  licenses, or external service accounts have been provisioned.

## CI gate

tests/test_product_gates.py covers the ten production boundaries in addition
to the existing unit/integration/regression suites.
