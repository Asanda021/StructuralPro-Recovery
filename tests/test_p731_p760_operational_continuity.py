from datetime import datetime, timezone
from core.platform.incident_readiness_v1 import assess_incident_readiness, require_incident_readiness
from core.platform.recovery_drill_v1 import assess_recovery_drill, require_recovery_drill
from core.platform.rollback_gate_v1 import assess_rollback, require_rollback
from core.platform.backup_integrity_v1 import BackupEvidence, RestoreEvidence, ProjectIntegrityEvidence

def test_incident_readiness_is_fail_closed_and_stable():
    checks = {"backup_available": True, "integrity_check": True, "safe_mode_available": True}
    a = require_incident_readiness(checks)
    b = require_incident_readiness(dict(reversed(list(checks.items()))))
    assert a.ready and a.blockers == () and a.fingerprint == b.fingerprint

def test_incident_readiness_blocks_missing_check():
    result = assess_incident_readiness({"backup_available": True})
    assert not result.ready
    assert "integrity_check" in result.blockers

def test_recovery_drill_composes_existing_integrity_boundary():
    now = datetime.now(timezone.utc).isoformat()
    backup = BackupEvidence("b1", "p1", "r1", now, "a" * 64)
    restore = RestoreEvidence("b1", "operator", now, "r2")
    integrity = ProjectIntegrityEvidence("p1", "b" * 64, "c" * 64, "r2", True)
    result = require_recovery_drill(backup, restore, integrity, project_id="p1")
    assert result.passed and result.blockers == ()

def test_recovery_drill_rejects_revision_mismatch():
    now = datetime.now(timezone.utc).isoformat()
    backup = BackupEvidence("b1", "p1", "r1", now, "a" * 64)
    restore = RestoreEvidence("b1", "operator", now, "r2")
    integrity = ProjectIntegrityEvidence("p1", "b" * 64, "c" * 64, "r3", True)
    result = assess_recovery_drill(backup, restore, integrity, project_id="p1")
    assert not result.passed and "revision_mismatch" in result.blockers

def test_rollback_is_fail_closed():
    result = require_rollback("1.2.0", "1.1.0", target_known_good=True,
                              backup_verified=True, migration_path_available=True,
                              engineering_regression_free=True)
    assert result.allowed

def test_rollback_blocks_unknown_target():
    result = assess_rollback("1.2.0", "1.1.0", target_known_good=False,
                             backup_verified=True, migration_path_available=True,
                             engineering_regression_free=True)
    assert not result.allowed and "target_not_known_good" in result.blockers
