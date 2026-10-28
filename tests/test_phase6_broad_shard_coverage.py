"""Proof that cross-shard artifacts cannot hide missing or duplicate tests."""
import json
from pathlib import Path
import pytest
from scripts.verify_phase6_broad_shards import cases, verify


def _write(folder, names, *, shard=None, full=False, manifest="a"*64):
    folder.mkdir(parents=True, exist_ok=True)
    stem = "phase6-broad-current" + ("-windows" if shard is not None else "")
    xml = folder / (stem + ".xml")
    xml.write_text("<testsuite>" + "".join(
        '<testcase classname="suite" name="' + str(x) + '"/>' for x in names
    ) + "</testsuite>")
    payload = {
        "overall_green": True, "pytest_exit_code": 0, "timed_out": False,
        "junit_report_written": True, "shard_count": 3 if shard is not None else 1,
        "shard_index": shard or 0, "current_test_modules_total": 3,
        "current_test_modules_in_shard": 1 if shard is not None else 3,
        "current_test_manifest_sha256": manifest, "stats": {"collected": len(names)},
    }
    (folder / (stem + ".json")).write_text(json.dumps(payload))


def test_junit_union_accepts_all_exact_cases(tmp_path):
    _write(tmp_path / "p6-broad-current-linux", ["a","b","c"])
    for i, name in enumerate("abc"):
        _write(tmp_path / f"p6-broad-current-windows-{i}", [name], shard=i)
    result = verify(tmp_path)
    assert result["verified"] and result["case_count"] == 3


@pytest.mark.parametrize("fault", ["missing","duplicate","wrong_manifest","failed_shard"])
def test_junit_union_detects_missing_duplicate_and_failed_shard(tmp_path, fault):
    _write(tmp_path / "p6-broad-current-linux", ["a","b","c"])
    for i,name in enumerate("abc"):
        values = ["a"] if fault == "duplicate" and i == 1 else ([] if fault == "missing" and i == 2 else [name])
        _write(tmp_path / f"p6-broad-current-windows-{i}", values, shard=i,
               manifest="b"*64 if fault == "wrong_manifest" and i == 1 else "a"*64)
    if fault == "failed_shard":
        path = tmp_path / "p6-broad-current-windows-2" / "phase6-broad-current-windows.json"
        data = json.loads(path.read_text()); data["overall_green"] = False; path.write_text(json.dumps(data))
    with pytest.raises((ValueError, FileNotFoundError)):
        verify(tmp_path)


def test_duplicate_junit_cases_fail_closed(tmp_path):
    path = tmp_path / "same.xml"
    path.write_text('<testsuite><testcase classname="x" name="y"/>'
                    '<testcase classname="x" name="y"/></testsuite>')
    with pytest.raises(ValueError, match="Duplicate"):
        cases(path)
