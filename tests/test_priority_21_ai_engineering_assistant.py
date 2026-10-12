"""Regression tests for Priority 21 — AI Engineering Assistant."""
from core.ai.engineering_assistant import EngineeringAssistant

def test_classification_and_context_are_deterministic():
    a=EngineeringAssistant()
    assert a.classify("بررسی متره پروژه")[0] == "takeoff_review"
    ctx=a.context({"id":"P21","name":"Demo","takeoffs":[1],"boq":[1,2]})
    assert ctx["project_id"]=="P21" and ctx["takeoff_count"]==1 and ctx["boq_count"]==2

def test_project_review_uses_validation_evidence_without_mutation():
    a=EngineeringAssistant(); project={"id":"P21","name":"Demo","takeoffs":[],"boq":[]}
    result=a.respond("بررسی پروژه",project=project,validator=lambda _:{"errors":[{"code":"x"}],"warnings":[],"score":80})
    assert result.intent=="project_review" and "1 خطای داده" in result.text
    assert result.evidence[-1]["type"]=="validation" and project["takeoffs"]==[]

def test_consequential_request_is_confirmation_gated():
    result=EngineeringAssistant().respond("متره را اجرا و ثبت کن",project={"name":"Demo"})
    assert result.requires_confirmation is True
    assert result.proposals[0]["action"]=="user_confirmation_required"

def test_model_review_is_read_only():
    result=EngineeringAssistant().respond("BIM مدل را بررسی کن",project={"model_sources":[1],"model_objects":[1,2]})
    assert result.intent=="model_review" and result.requires_confirmation is False and result.deterministic is True
