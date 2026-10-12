"""Unit tests that exercise the read-only forensic checks without GitHub access."""
import importlib.util
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("forensic", ROOT / "scripts/audit_historical_recovery.py")
forensic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forensic)

def test_git_blob_sha_known_value():
    assert forensic.git_blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"

def test_fail_closed_for_wrong_archive_prefix():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "core/takeoff").mkdir(parents=True)
        (root / "app").mkdir()
        zpath = root / "fake.zip"
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("wrong-branch/foo.py", "print(1)")
        try:
            forensic.audit(root, zpath)
        except ValueError as e:
            assert "root" in str(e)
        else:
            raise AssertionError("wrong archive accepted")

def test_recovery_shas_are_distinct():
    assert forensic.HISTORICAL_MAIN_SHA_REPORTED != forensic.HISTORICAL_PR462_SHA
    assert forensic.HISTORICAL_PR462_SHA != forensic.HISTORICAL_PR481_SHA_REPORTED

def test_original_pr481_missing_test_set_has_eight_unique_paths():
    assert len(forensic.PR481_EXPECTED_TESTS) == len(set(forensic.PR481_EXPECTED_TESTS)) == 8

def test_original_finishing_codes_are_unique():
    assert len(forensic.FINISH_13) == len(set(forensic.FINISH_13)) == 13