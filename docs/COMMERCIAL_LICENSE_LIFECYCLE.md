# Commercial License Lifecycle

## Purpose

This boundary defines the client-side lifecycle checks required before StructuralPro commercial activation is enabled.

The desktop client remains offline-first. License verification does not require a network connection and does not contain a private signing key.

## License record

A license record contains:
- product
- license ID
- customer
- optional ISO-8601 expiration date
- feature entitlements
- issuer

The canonical payload is deterministic and its SHA-256 fingerprint can be used as stable evidence for the exact license payload.

## Verification policy

The client verifier fails closed when:
- the product does not match the expected product;
- the license ID or customer is blank;
- the issuer is blank;
- the license ID is revoked;
- an expiration date is malformed;
- the license has expired;
- feature entitlements contain duplicates;
- the signature is missing;
- signature verification raises an exception or returns false.

An empty expiration date represents a perpetual license record. A date-only expiration is valid through that date and becomes expired on the following date.

## Revocation boundary

Revocation is represented as an injected set of license IDs. The repository does not invent a network revocation service.

A production licensing service may supply the current revocation set through an approved channel. Offline clients must retain the last explicitly provisioned policy; absence of a network connection must not silently turn an invalid local record into a valid one.

## Entitlements

Feature checks use the exact feature identifiers contained in the signed license payload. The application should gate optional commercial functionality through the `has_feature()` method rather than duplicating license logic inside UI modules.

## Activation boundary

Activation storage, customer support workflow, issuer infrastructure, payment processing and certificate/key management remain outside the desktop client.

The private signing key must remain outside the repository, installer, executable and client configuration. Only the public verification material required by the production verifier may be distributed to the client.

## Evidence

Commercial activation should retain enough non-secret evidence to reproduce the decision:
- license ID;
- license fingerprint;
- product;
- issuer;
- effective/expiration policy;
- entitlement identifiers;
- verification result;
- application version.

Do not store private signing material, passwords, access tokens or unrelated customer secrets in diagnostic logs.
