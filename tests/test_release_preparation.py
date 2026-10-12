from core.platform.release_preparation_v1 import evaluate_release_preparation,require_release_preparation
VALID={"version":"0.1.0","candidate_fingerprint":"a"*64,"release_notes":"ready","rollback_plan":"restore previous stable commit","provenance":"main merge SHA"}
def test_valid_and_deterministic():
 a=evaluate_release_preparation(VALID); b=evaluate_release_preparation(dict(reversed(list(VALID.items()))))
 assert a.ready and not a.blockers and a.fingerprint==b.fingerprint
def test_missing_fails_closed():
 r=evaluate_release_preparation({**VALID,"rollback_plan":""}); assert not r.ready
def test_unknown_fails_closed():
 r=evaluate_release_preparation({**VALID,"extra":"x"}); assert not r.ready and "unknown field: extra" in r.blockers
def test_mutation_changes_fingerprint():
 assert evaluate_release_preparation(VALID).fingerprint != evaluate_release_preparation({**VALID,"version":"0.1.1"}).fingerprint
def test_require_raises():
 try: require_release_preparation({**VALID,"provenance":""})
 except ValueError: pass
 else: raise AssertionError("expected ValueError")
