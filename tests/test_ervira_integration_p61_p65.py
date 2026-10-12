import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONTRACTS = ROOT / "contracts" / "ervira"


def load(n):
    return json.loads((CONTRACTS / f"p{n:02d}.json").read_text(encoding="utf-8"))


def test_p61_p65_governance_is_implemented_but_release_closed():
    for n in range(61, 66):
        c = load(n)
        assert c["status"] == "implemented"
        assert c["runtime_status"] == "implemented"
        assert c["release_ready"] is False


def test_p61_registry_is_build_evidence_bound():
    rules = load(61)["rules"]
    assert any("source commit" in r for r in rules)
    assert any("verified build output" in r for r in rules)


def test_p62_version_is_canonical_and_synchronized():
    rules = load(62)["rules"]
    assert any("canonical VERSION" in r for r in rules)
    assert any("packaged VERSION" in r for r in rules)


def test_p63_build_is_commit_bound_and_validated():
    rules = load(63)["rules"]
    assert any("exact source commit" in r for r in rules)
    assert any("Windows build validation" in r for r in rules)


def test_p64_release_notes_are_version_and_capability_bound():
    rules = load(64)["rules"]
    assert any("canonical VERSION" in r for r in rules)
    assert any("unverified features" in r for r in rules)


def test_p65_artifacts_are_checksum_bound_and_fail_closed():
    rules = load(65)["rules"]
    assert any("SHA-256" in r for r in rules)
    assert any("fail closed" in r for r in rules)
