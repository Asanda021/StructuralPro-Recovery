import pytest
from core.ai import AIOrchestrator, AISuggestion

def test_ai_orchestrator_is_review_first():
 r=AIOrchestrator().analyze_revision([{"price_code":"A","quantity":10}],[{"price_code":"A","quantity":12}]); assert r[0].payload["delta"]==2 and r[0].requires_confirmation and r[0].confidence==1.0

def test_drawing_and_takeoff_preserve_source_and_confirmation():
 class E: layer="beam"; source_id="D1"; data={"source_id":"D1","length":4}
 ai=AIOrchestrator(); d=ai.understand_drawing([E()]); t=ai.suggest_takeoff([E()]); assert d[0].source_ids==("D1",) and t[0].source_ids==("auto:beam",) and t[0].requires_confirmation

def test_nl_query_uses_only_context():
 ai=AIOrchestrator(); assert ai.query("جمع مبلغ",{"rows":[{"total":100},{"total":25}]})["answer"]==125; assert ai.query("چه چیزی؟",{"rows":[]})["supported"] is False

def test_confidence_boundary():
 with pytest.raises(ValueError): AISuggestion("x",{},1.1)
