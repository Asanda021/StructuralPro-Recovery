# StructuralPro Licensing and License Architecture

## Application license boundary

StructuralPro contains an offline license data model and verification boundary in core/platform/release.py.

The client stores license metadata and can calculate a deterministic fingerprint from the canonical license payload. The commercial lifecycle boundary validates expiration, revocation, entitlement uniqueness and fail-closed identity/signature conditions.

## Security rule

The desktop application must not contain a private/signing secret. License verification is injected so a production asymmetric-signature verifier can be supplied using a public verification key.

## Production licensing

Before commercial licensing is enabled:
1. Define the authoritative license issuer.
2. Select the asymmetric signature scheme.
3. Store the private signing key outside the application repository and build artifacts.
4. Embed/distribute only the public verification material required by the client.
5. Define license fields, expiration behavior, feature entitlements and revocation policy.
6. Test invalid signatures, modified payloads, expired licenses and unsupported products.
7. Document the customer activation/support workflow.

The client-side lifecycle checks are implemented and regression-tested in `core/platform/release.py` and `tests/test_priority_11_license_lifecycle.py`. Issuer infrastructure, payment processing, customer activation support and production key provisioning remain external commercial services.

## Third-party licensing

Every bundled dependency, converter, model and dataset must be checked for redistribution and commercial-use compatibility.

In particular:
- official price-list data must have a verified/licensed source;
- GGUF model weights must have compatible redistribution terms;
- DWG conversion software/SDKs must have compatible terms.

This repository must not fabricate official price data or imply that a third-party license has been obtained when it has not.
