"""Read-only acquisition probe for a genuinely independent historical DWG.

This does NOT certify geometry, measured quantities, BOQ, or production readiness.
No executable/installer is built, no project state is mutated, no raw DWG is uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

CATALOG = "https://www.innerscene.com/tools/library/drawings/cattleguard-foundation-usfs-waw0025a-103df315"
SOURCE = "https://www.innerscene.com/api/library/cattleguard-foundation-usfs-waw0025a-103df315/download"
ALLOWED_HOSTS = frozenset({"www.innerscene.com", "files.innerscene.com"})
MAX_BYTES = 2 * 1024 * 1024
SUPPORTED_BRIDGE_SIGNATURES = frozenset({"AC1014", "AC1015", "AC1018", "AC1021", "AC1024", "AC1027", "AC1032"})
LEGACY_SIGNATURES = frozenset({"AC1009", "AC1012"})


def approved_url(url: str) -> bool:
    target = urlsplit(url)
    return target.scheme == "https" and target.hostname in ALLOWED_HOSTS and target.username is None and target.password is None and target.port in (None, 443)


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not approved_url(newurl):
            raise ValueError("DWG redirect left the allowed HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def inspect_dwg(data: bytes) -> dict:
    if not isinstance(data, bytes) or len(data) < 1024 or len(data) > MAX_BYTES:
        raise ValueError("DWG size is outside the bounded candidate envelope")
    try:
        signature = data[:6].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("DWG has no valid ASCII version signature") from exc
    if signature not in SUPPORTED_BRIDGE_SIGNATURES | LEGACY_SIGNATURES:
        raise ValueError("Unknown or unsupported DWG signature: " + repr(signature))
    eligible = signature in SUPPORTED_BRIDGE_SIGNATURES
    return {
        "sha256": hashlib.sha256(data).hexdigest(), "dwg_signature": signature,
        "bytes": len(data), "eligible_for_approved_acadsharp_versions": eligible,
        "compatibility": "POTENTIAL_VERSION_ONLY_NOT_CONVERTED" if eligible else "LEGACY_VERSION_OUTSIDE_APPROVED_BRIDGE",
    }


def probe(url: str = SOURCE) -> dict:
    if url != SOURCE or not approved_url(url):
        raise ValueError("Only the recorded public source is permitted")
    opener = build_opener(RestrictedRedirect())
    request = Request(url, headers={"User-Agent": "StructuralPro-source-audit/1.0", "Accept": "application/octet-stream,*/*"})
    with opener.open(request, timeout=35) as response:
        final_url = response.geturl()
        if not approved_url(final_url):
            raise ValueError("DWG response came from an unapproved source")
        data = response.read(MAX_BYTES + 1)
    facts = inspect_dwg(data)
    return {
        "status": "SOURCE_BINARY_PROBED_ONLY_NOT_ENGINEERING_ACCEPTANCE",
        "source_id": "USFS-WAW0025A-1995",
        "historical_author": "USDA Forest Service (as described in source catalogue)",
        "catalog_url": CATALOG,
        "request_url": url,
        "response_url": final_url,
        "licence_note": "US federal government work; public domain in US, other jurisdictions unassessed",
        "source_sha256_pinned_independently": False,
        "independent_geometry_oracle_available": False,
        "dwg_to_dxf_native_conversion_tested": False,
        "boq_commit_tested": False,
        "release": "NO_GO",
        **facts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
