"""SQLite/cache parity for JSON-compatible graphical coordinates."""
from core.projects.store import ProjectStore


def test_cached_project_equals_reopened_project_with_tuple_geometry(tmp_path):
    path = tmp_path / 'projects.sqlite'
    store = ProjectStore(path)
    try:
        store.save('P', {'id': 'P', 'name': 'آزمون', 'takeoffs': [], 'boq': [],
                         'drawing_sessions': {'S': {'geometry': ((1, 2), (3, 4))}}})
        cached = store.get('P')
        other = ProjectStore(path)
        try:
            assert other.get('P') == cached
        finally:
            other.close()
        store._cache.clear()
        assert store.get('P') == cached
    finally:
        store.close()
