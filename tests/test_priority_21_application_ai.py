"""Application integration tests for Priority 21."""
from core.platform.application import StructuralProApp

def test_application_ai_assistant_is_read_only_and_contextual(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("پروژه P21","P21")
    result=app.ai_assistant_respond("P21","بررسی پروژه")
    assert result["offline"] is True
    assert result["intent"]=="project_review"
    assert result["evidence"][0]["type"]=="project_context"
    assert result["evidence"][0]["data"]["project_id"]=="P21"

def test_application_ai_assistant_confirmation_gate(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project("پروژه P21","P21")
    result=app.ai_assistant_respond("P21","متره را اجرا و ثبت کن")
    assert result["requires_confirmation"] is True
    assert result["proposals"][0]["action"]=="user_confirmation_required"
    assert app.open_project("P21")["takeoffs"]==[]
