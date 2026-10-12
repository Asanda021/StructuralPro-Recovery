import pytest
from core.ux.ux_workflow_v2 import *

def test_workflow_dashboard_and_onboarding():
    wf=build_workflow([WorkflowStep("a","Import","Ctrl+I"),WorkflowStep("b","Review")])
    db=build_dashboard([DashboardCard("kpi","Items","12","src")])
    assert len(wf)==2 and db[0]["value"]=="12" and onboarding_steps()[0]=="create_project"

def test_ux_contract_fails_closed():
    with pytest.raises(ValueError): build_workflow([WorkflowStep("a","A"),WorkflowStep("a","B")])
    with pytest.raises(ValueError): build_dashboard([DashboardCard("x","","1","s")])
