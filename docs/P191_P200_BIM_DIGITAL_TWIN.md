# P191-P200 — BIM / Digital Twin Foundation

This phase turns the existing IFC/model-registry boundaries into a deterministic,
auditable project graph. It does not replace the existing IFC adapter or invent
engineering quantities.

## Scope
- persistent-style canonical nodes for source, BIM object, 2D evidence, quantity, BOQ and estimate;
- deterministic node/edge identities;
- source/object/quantity/BOQ/estimate lineage;
- 2D-to-3D representation links;
- deterministic revision impact traversal;
- stable graph fingerprint;
- fail-closed validation for unknown identities and missing explicit quantities.

## Engineering rules
1. No quantity is inferred: quantity nodes require an explicit numeric quantity.
2. Unknown source/object/BOQ/estimate relationships are rejected.
3. Duplicate nodes and invalid edges are rejected.
4. Impact traversal is deterministic and does not mutate project data.
5. Existing IFC and takeoff modules remain unchanged and are consumed as upstream evidence.

## Phase mapping
P191: canonical twin node contract
P192: deterministic identity
P193: source → BIM object lineage
P194: object → quantity lineage
P195: 2D ↔ 3D identity link
P196: quantity → BOQ lineage
P197: BOQ → estimate lineage
P198: revision impact traversal
P199: deterministic fingerprint / audit surface
P200: fail-closed integration tests and production gate
