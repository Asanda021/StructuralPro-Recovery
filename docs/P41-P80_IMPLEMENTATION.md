# StructuralPro P41–P80 implementation

This release hardens the first five roadmap blocks without fabricating external dependencies or official datasets.

## P41–P50 — Windows product
- Windows packaging validates the canonical VERSION.
- Optional packaged executable smoke test is available with `-SmokeTest`.
- Optional Inno Setup build is available with `-BuildInstaller`.
- SHA-256 checksums are generated for the executable and installer.
- The installer remains lowest-privilege by default.

## P51–P60 — PDF/DWG/DXF
- PDF text-derived quantities remain review-required.
- PDF scale detection reports unknown/ambiguous instead of silently choosing a scale.
- Graphical PDF measurements require an explicit scale calibration.
- DWG uses an explicit offline converter boundary; absence of a converter fails closed.
- DXF geometry is normalized to metres where CAD units are known.
- CAD/PDF candidates retain source, sheet/page and review provenance.

## P61–P70 — Full AEC takeoff
The desktop takeoff surface now exposes a discipline selector covering:
- معماری
- سازه بتنی
- سازه فولادی
- بنا و دیوارچینی
- سازه چوبی
- سازه مرکب
- تأسیسات مکانیکی
- تأسیسات برقی
- بهسازی و مرمت
- محوطه و عملیات بیرونی

The selector is additive and does not replace the existing deterministic quantity formulas.

## P71–P80 — Pricebook
- User-supplied CSV import remains available.
- Imports are schema/number validated and fingerprinted with SHA-256.
- Official/verified mode requires a registered source plus matching checksum.
- No official price is fabricated when a verified dataset is not present.
- Each successful import returns a receipt containing source, year, discipline, file and checksum.

## Acceptance gates
The repository includes `tests/test_p41_p80_product_gates.py` for the release contract, fail-closed drawing behavior and price provenance invariants.

External provisioning is still explicit: an official pricebook file and any redistributable DWG converter must actually be supplied/verified before they can be marked as official/verified.
