import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
C = ROOT / "contracts" / "ervira"


def load(n):
    return json.loads((C / f"p{n:02d}.json").read_text(encoding="utf-8"))


def test_p66_p70_are_implemented_but_release_closed():
    for n in range(66, 71):
        x = load(n)
        assert x["status"] == "implemented"
        assert x["runtime_status"] == "implemented"
        assert x["release_ready"] is False


def test_p66_hash_verification_blocks_mismatch():
    r = load(66)["rules"]
    assert any("SHA-256" in x for x in r)
    assert any("mismatch blocks release registration" in x for x in r)


def test_p67_download_is_entitlement_bound_and_fail_closed():
    r = load(67)["rules"]
    assert any("entitlement-bound" in x for x in r)
    assert any("fails closed" in x for x in r)


def test_p68_installer_delivery_is_windows_validated():
    r = load(68)["rules"]
    assert any("Windows installer" in x for x in r)
    assert any("Windows runner" in x for x in r)


def test_p69_installation_detection_requires_successful_smoke():
    r = load(69)["rules"]
    assert any("installed executable" in x for x in r)
    assert any("smoke test" in x for x in r)


def test_p70_release_is_not_customer_live_from_ci_alone():
    x = load(70)
    assert any("not customer-live" in r for r in x["rules"])
    assert any("release_ready becomes true" in r for r in x["rules"])
    assert x["release_ready"] is False
