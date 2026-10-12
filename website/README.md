# StructuralPro Website

This directory contains the canonical website information model for the StructuralPro ecosystem site. UI implementations must consume the canonical navigation, product taxonomy and locale content rather than duplicating them.

## Source of truth
- `data/products.json` — 29 specialized products + 1 Enterprise platform
- `data/navigation.json` — primary navigation and actions
- `data/i18n.en.json` — English foundation copy
- `data/i18n.fa.json` — Persian foundation copy and RTL metadata

The website is intentionally being built in phases. Product binaries, real downloads and unreleased capabilities must not be represented as available merely because they exist in the information architecture.
