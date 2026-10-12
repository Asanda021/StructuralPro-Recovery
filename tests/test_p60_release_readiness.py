from core.release.release_readiness_v1 import ReleaseArtifact, InstallCheck, assess_release, validate_release
def artifact(): return ReleaseArtifact("structuralpro","1.0.0","a"*64,"linux","2026-10-04T00:00:00Z")
def check(status="pass"): return InstallCheck("structuralpro","linux",status,"installation-log-ref")
def test_deterministic_go():
    assert assess_release((artifact(),),(check(),))==assess_release((artifact(),),(check(),))
    assert assess_release((artifact(),),(check(),)).decision=="go"
def test_missing_evidence_fails_closed():
    try: validate_release((),())
    except ValueError: pass
    else: raise AssertionError
def test_invalid_sha_fails_closed():
    try: validate_release((ReleaseArtifact("x","1","bad","linux","t"),),(check(),))
    except ValueError: pass
    else: raise AssertionError
def test_fail_is_no_go(): assert assess_release((artifact(),),(check("fail"),)).decision=="no_go"
def test_unknown_needs_evidence(): assert assess_release((artifact(),),(check("needs_evidence"),)).decision=="needs_evidence"
