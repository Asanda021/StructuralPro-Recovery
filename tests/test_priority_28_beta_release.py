import pytest
from core.platform.beta import beta_gate,beta_label
def test_beta_gate_requires_all_release_surfaces():
    assert not beta_gate(version_valid=True,golden_ready=True,docs_ready=True,packaging_ready=False).ready
    assert beta_gate(version_valid=True,golden_ready=True,docs_ready=True,packaging_ready=True).ready
def test_beta_gate_reports_blockers():
    g=beta_gate(version_valid=True,golden_ready=True,docs_ready=True,packaging_ready=True,blocking_issues=["installer"])
    assert not g.ready and g.blocking_issues==("installer",)
def test_beta_label_validates_canonical_version():
    assert beta_label("0.1.0")=="StructuralPro 0.1.0 Beta"
    with pytest.raises(ValueError): beta_label("v0.1.0")
