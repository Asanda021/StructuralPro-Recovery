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
STUDIO_SOURCE = "https://www.innerscene.com/api/library/studio-floor-plan-193f4ec8/download"
SOURCES = {
    "usfs_legacy": {
        "url": SOURCE, "source_id": "USFS-WAW0025A-1995",
        "expected_sha256": "8875121bf851850520ea9c1c5a125a470dc62c59690d38b796e0ea77b98e7bd5",
        "catalog": CATALOG, "author": "USDA Forest Service (source catalogue)",
        "license": "US federal government work; status outside the US not established",
        "independent_real_site": False,
    },
    "studio_cc0": {
        "url": STUDIO_SOURCE, "source_id": "INNERSCENE-STUDIO-FLOOR-PLAN-2026",
        "expected_sha256": "e2dd2e3b9b88022dddd73ad3dee88e99986613165393ddf2c6ff70453a4897ce",
        "catalog": "https://www.innerscene.com/tools/library/drawings/studio-floor-plan-193f4ec8",
        "author": "Innerscene (publisher attribution)",
        "license": "CC0 as stated by source page; legal review not performed",
        "independent_real_site": False,
    },
}
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
    selected = next((item for item in SOURCES.values() if item["url"] == url), None)
    if selected is None or not approved_url(url):
        raise ValueError("Only explicitly recorded public source URLs are permitted")
    opener = build_opener(RestrictedRedirect())
    request = Request(url, headers={"User-Agent": "StructuralPro-source-audit/1.0", "Accept": "application/octet-stream,*/*"})
    with opener.open(request, timeout=35) as response:
        final_url = response.geturl()
        if not approved_url(final_url):
            raise ValueError("DWG response came from an unapproved source")
        data = response.read(MAX_BYTES + 1)
    facts = inspect_dwg(data)
    if facts["sha256"] != selected["expected_sha256"]:
        raise ValueError("Public DWG source checksum changed since independent OS readings")
    return {
        "status": "SOURCE_BINARY_PROBED_ONLY_NOT_ENGINEERING_ACCEPTANCE",
        "source_id": selected["source_id"],
        "historical_author": selected["author"],
        "catalog_url": selected["catalog"],
        "request_url": url,
        "response_url": final_url,
        "licence_note": selected["license"],
        "independent_real_site_verified": selected["independent_real_site"],
        "source_sha256_pinned_in_test": True,
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
    parser.add_argument("--source-id", choices=tuple(SOURCES), default="usfs_legacy")
    args = parser.parse_args()
    evidence = probe(SOURCES[args.source_id]["url"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
