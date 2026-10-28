"""The full broad Windows shard partition must not lose any modules."""
from pathlib import Path
import pytest
from scripts.run_quarantined_workflow_qa import HISTORICAL_TESTS, current_test_modules


def test_shard_manifest_is_exhaustive_stable_and_without_historical(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    for i in range(23):
        (tests / f"test_active_{i:02d}.py").write_text("def test_x(): pass\n")
    archived = Path(HISTORICAL_TESTS[0])
    (tests / archived.name).write_text("def test_archived(): pass\n")
    lists = [current_test_modules(tmp_path, shard_count=3, shard_index=i) for i in range(3)]
    manifests = [item[2] for item in lists]
    assert len(set(manifests)) == 1
    original = lists[0][0]
    assert len(original) == 23
    assert all(len(x[0]) == 23 for x in lists)
    combined = [p for entry in lists for p in entry[1]]
    assert len(combined) == len(set(combined)) == 23
    assert set(combined) == set(original)
    assert all(archived.name not in path for path in combined)
    assert current_test_modules(tmp_path)[1] == original


@pytest.mark.parametrize("count,index", [(0, 0), (1, -1), (2, 2), (True, 0), (2, False)])
def test_invalid_shard_selection_fails_closed(tmp_path, count, index):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text("def test_x(): pass\n")
    with pytest.raises((ValueError, RuntimeError)):
        current_test_modules(tmp_path, shard_count=count, shard_index=index)
