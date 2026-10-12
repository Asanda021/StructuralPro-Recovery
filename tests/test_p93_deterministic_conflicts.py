import pytest

from core.sync.conflicts import merge_dict, resolve_conflicts


def test_recursive_merge_preserves_non_conflicting_nested_changes():
    merged, conflicts = merge_dict(
        {"meta": {"name": "A", "version": 1}},
        {"meta": {"name": "B", "version": 1}},
        {"meta": {"name": "A", "version": 2}},
    )
    assert conflicts == []
    assert merged == {"meta": {"name": "B", "version": 2}}


def test_recursive_merge_records_stable_nested_conflict_path():
    merged, conflicts = merge_dict(
        {"meta": {"name": "A"}},
        {"meta": {"name": "B"}},
        {"meta": {"name": "C"}},
    )
    assert conflicts == ["meta.name"]
    assert merged["meta"]["name"]["_conflict"]["local"] == "B"
    assert merged["meta"]["name"]["_conflict"]["remote"] == "C"


def test_nested_conflict_can_be_resolved_without_touching_sibling():
    project, conflicts = merge_dict(
        {"meta": {"name": "A", "version": 1}},
        {"meta": {"name": "B", "version": 2}},
        {"meta": {"name": "C", "version": 1}},
    )
    assert conflicts == ["meta.name"]
    resolved = resolve_conflicts(project, {"meta.name": "remote"})
    assert resolved == {"meta": {"name": "C", "version": 2}}


def test_invalid_types_and_choices_fail_closed():
    with pytest.raises(TypeError):
        merge_dict([], {}, {})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="local, remote or base"):
        resolve_conflicts({"x": {"_conflict": {"local": 1, "remote": 2, "base": 0}}}, {"x": "bad"})
