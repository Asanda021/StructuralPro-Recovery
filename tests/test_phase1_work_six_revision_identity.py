"""Numeric equality does not establish revision identity."""
from copy import deepcopy
import pytest
from core.takeoff.building_six_family_ownership_chat import audit
from test_phase1_six_family_ownership_chat import sample

@pytest.mark.parametrize('revision',[True,1.0])
def test_revision_token_requires_actual_integer(revision):
    d,p,files=sample();d['links'][0]['record_revision']=revision
    before=deepcopy((d,p,files));out=audit(d,p,documents=files)
    assert out['document_consistent'] is False
    assert out['totals_not_payable']=={} and out['physical_owner_count']==0
    assert out['ready'] is False and out['commit_allowed'] is False and out['payable_rows']==[]
    assert (d,p,files)==before
