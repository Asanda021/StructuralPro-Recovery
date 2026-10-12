# P106-P110 Production Acceptance

## What these priorities prove

**P106 — Real Project Validation:** a deterministic acceptance pack of five representative concrete-building cases is executed through the same quantity and validation surfaces used by the product. These are repository acceptance fixtures, not a claim that an unidentified external customer project was imported.

**P107 — Engineering Depth:** each case exercises concrete volume, rebar weight, stock-bar/cut planning and roof-specific quantity logic where applicable. Results are deterministic and compared with expected golden values.

**P108 — CAD/DWG Production Boundary:** DWG capability is detected transparently. If a native reader or configured offline converter exists, it is reported; otherwise the system explicitly reports the missing backend. No fake DWG support is claimed.

**P109 — BIM/IFC Production Integrity:** the normalized BIM model is round-tripped through a signed/digested manifest and verified for integrity. Native IFC import/export remains dependent on the installed IFC runtime.

**P110 — Production Takeoff → BOQ → Estimate:** representative cases run end-to-end through takeoff, BOQ, pricing and estimate validation. Invalid data fails closed.

## External evidence boundary

P106 fixtures are controlled acceptance data, not a substitute for a customer-supplied real project. Final commercial acceptance still needs real project files and authorized Iranian price data. DWG and native IFC production also require their external runtime dependencies when those formats are shipped.
