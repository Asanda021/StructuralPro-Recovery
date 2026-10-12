from core.verification.production_regression_v1 import ProjectArtifact, QuantityCheck, evaluate_project, validate_artifacts

def artifact():
    return ProjectArtifact("PROJECT-001", "pdf", "external://project-001/drawings.pdf", "a" * 64, "2026-10-04T00:00:00Z")

def test_real_world_evaluation_is_deterministic():
    checks = (QuantityCheck("concrete", 120.0, 118.0, "m3"), QuantityCheck("rebar", 10000.0, 10100.0, "kg"))
    first = evaluate_project("PROJECT-001", (artifact(),), checks)
    second = evaluate_project("PROJECT-001", (artifact(),), checks)
    assert first == second
    assert first.check_count == 2
    assert first.artifact_count == 1
    assert first.absolute_error_total == 102.0

def test_missing_artifacts_fail_closed():
    try:
        evaluate_project("PROJECT-001", (), (QuantityCheck("concrete", 1.0, 1.0, "m3"),))
    except ValueError as exc:
        assert "artifacts" in str(exc)
    else:
        raise AssertionError("missing real-world evidence must fail closed")

def test_invalid_hash_fails_closed():
    try:
        validate_artifacts((ProjectArtifact("PROJECT-001", "pdf", "external://drawings.pdf", "not-a-hash", "2026-10-04T00:00:00Z"),))
    except ValueError as exc:
        assert "sha256" in str(exc)
    else:
        raise AssertionError("invalid artifact hash must fail closed")

def test_zero_baseline_is_not_silently_divided():
    result = QuantityCheck("area", 0.0, 1.0, "m2")
    assert result.relative_error is None
