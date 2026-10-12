from core.estimate.pricebook_artifact_v1 import release_gate, verify_artifact

def test_release_gate_requires_real_file_hash():
    assert not release_gate(rows=[1],artifact_verification=None)["green"]

def test_verification_requires_sha256():
    try: verify_artifact(expected_year=1404,expected_discipline="ابنیه",file_sha256="bad",source_url="https://example.com")
    except ValueError: return
    assert False
