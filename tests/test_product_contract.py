import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "product-contract.json"
VERSION = ROOT / "VERSION"


def test_product_contract_matches_version():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    version = VERSION.read_text(encoding="utf-8").strip()
    assert contract["product_id"] == "structuralpro"
    assert contract["product_name"] == "StructuralPro"
    assert contract["parent_platform"] == "ERVIRA"
    assert contract["product"]["current_version"] == version
    assert contract["release"]["version"] == version


def test_product_contract_has_unique_capability_ids():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    ids = [item["id"] for item in contract["capabilities"]]
    assert ids
    assert len(ids) == len(set(ids))
    assert {item["status"] for item in contract["capabilities"]} <= {"available", "integration", "planned"}


def test_unpublished_release_cannot_expose_download():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    release = contract["release"]
    if release["publication_status"] != "published":
        assert release["download"]["enabled"] is False
        assert release["download"]["windows_installer"] is None
        assert release["download"]["sha256"] is None


def test_editions_are_explicitly_gated():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert [item["id"] for item in contract["editions"]] == ["light", "standard", "pro", "enterprise"]
    for edition in contract["editions"]:
        if edition["status"] != "available":
            assert edition["features"] == []
