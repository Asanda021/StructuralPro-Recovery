# Phase 21 — DWG/DXF

## Status
Implementation scope for CAD ingestion is frozen to deterministic extraction.

### Implemented
- DXF import with ezdxf
- DXF version capture
- drawing units from $INSUNITS
- layers
- blocks
- lines
- polylines
- arcs
- circles
- dimensions
- text/MTEXT metadata
- block inserts and transforms
- object counting
- entity handles
- geometry metrics where the source entity exposes them
- layer index
- deterministic source fingerprint
- exportable CAD payload
- validation and fail-closed behavior

### DWG boundary
Native DWG is not decoded by ezdxf. StructuralPro therefore requires an explicit DWG backend adapter for native DWG decoding. It never silently converts DWG, guesses geometry, units, or scale. The backend result is validated before entering the takeoff pipeline.

### Safety rule
Unresolved units fail closed. CAD geometry is evidence; engineering quantities are not invented from ambiguous data.

### Downstream contract
The extraction payload is designed to feed:
CAD → drawing intelligence → measurement → takeoff → BOQ → estimate → report.

### Verification gate
Phase 21 is green only after:
1. Implementation
2. Dedicated tests
3. Full regression
4. CI
5. Merge to main
6. Post-merge main verification
