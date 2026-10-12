import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
C = ROOT / "contracts" / "ervira"


def load(n):
    return json.loads((C / f"p{n:02d}.json").read_text(encoding="utf-8"))


def test_p71_p75_are_implemented_but_release_closed():
    for n in range(71, 76):
        x = load(n)
        assert x["status"] == "implemented"
        assert x["runtime_status"] == "implemented"
        assert x["release_ready"] is False


def test_p71_documentation_is_versioned_and_machine_readable():
    r = load(71)["rules"]
    assert any("versioned" in x for x in r)
    assert any("machine-readable" in x for x in r)


def test_p72_guides_match_canonical_version():
    r = load(72)["rules"]
    assert any("Persian and English" in x for x in r)
    assert any("canonical release version" in x for x in r)


def test_p73_integrations_are_auth_bound_and_secret_safe():
    r = load(73)["rules"]
    assert any("authentication and entitlement boundaries" in x for x in r)
    assert any("production secrets" in x for x in r)


def test_p74_documentation_is_version_synchronized():
    r = load(74)["rules"]
    assert any("canonical VERSION" in x for x in r)
    assert any("unreleased features" in x for x in r)


def test_p75_documentation_gate_is_fail_closed():
    x = load(75)
    assert any("customer release remains fail-closed" in r for r in x["rules"])
    assert x["release_ready"] is False


# CI retrigger marker: no runtime behavior change.
