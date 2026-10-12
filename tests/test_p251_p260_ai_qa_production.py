from core.ai.qa_production_v1 import QAFinding,AIQAGate
import pytest
def checker(p): return p.get("findings",[])
def test_accept_warning_and_ai_separation():
 r=AIQAGate(checker).review({"findings":[{"severity":"warning","code":"w","message":"review"}]},ai_notes=["note"])
 assert r["accepted"] and r["ai_notes_are_non_authoritative"]
def test_error_rejects():
 r=AIQAGate(checker).review({"findings":[{"severity":"error","code":"e","message":"bad"}]})
 assert not r["accepted"]
def test_invalid_finding_fails():
 with pytest.raises(ValueError): AIQAGate(checker).review({"findings":[{"severity":"x","code":"e","message":"bad"}]})
def test_fingerprint():
 g=AIQAGate(checker); r=g.review({"findings":[]}); assert g.fingerprint(r)==g.fingerprint(r)